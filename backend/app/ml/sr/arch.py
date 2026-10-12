"""ESRGAN network architectures, implemented directly in PyTorch.

Follows Real-ESRGAN (Wang et al., ICCVW 2021, arXiv 2107.10833), the
practical successor to ESRGAN (Wang et al., ECCVW 2018, arXiv 1809.00219):

- Generator: RRDBNet -- Residual-in-Residual Dense Blocks, no batch norm,
  residual scaling 0.2. For 2x, the input is first pixel-unshuffled (each 2x2
  block becomes 4 channels), so the expensive trunk runs at half the input
  resolution and the network upsamples 4x from there -- the same trick
  Real-ESRGAN's x2 model uses. It is what makes training fit a 6GB GPU.
- Discriminator: U-Net with spectral normalisation. Gives a per-pixel
  real/fake map rather than one score per image, which gives the generator
  local feedback and trains more stably than ESRGAN's original VGG-style
  discriminator.

Written here rather than imported from `basicsr`/`realesrgan`: those packages
are not installed, and basicsr imports `torchvision.transforms.functional_tensor`,
which recent torchvision (0.28 here) no longer ships.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn
from torch.nn.utils.parametrizations import spectral_norm


def _scaled_kaiming_init(modules, scale: float) -> None:
    # ESRGAN's residual blocks start near identity: kaiming init scaled down,
    # so a deep stack of residual blocks does not blow up at initialisation.
    for module in modules:
        if isinstance(module, nn.Conv2d):
            nn.init.kaiming_normal_(module.weight)
            module.weight.data *= scale
            if module.bias is not None:
                module.bias.data.zero_()


class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)
        _scaled_kaiming_init([self.conv1, self.conv2, self.conv3, self.conv4, self.conv5], 0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat: int, num_grow_ch: int = 32) -> None:
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x


class RRDBNet(nn.Module):
    """Generator. Input (B, 3, H, W) in [0, 1] -> output (B, 3, H*scale, W*scale).
    For scale=2, H and W must be even (upscale.py pads to guarantee it)."""

    def __init__(self, scale: int = 2, num_feat: int = 64, num_block: int = 16, num_grow_ch: int = 32) -> None:
        super().__init__()
        if scale not in (2, 4):
            raise ValueError(f"scale must be 2 or 4, got {scale}")
        self.scale = scale
        in_ch = 3 * 4 if scale == 2 else 3
        self.conv_first = nn.Conv2d(in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, 3, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = F.pixel_unshuffle(x, 2) if self.scale == 2 else x
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


class UNetDiscriminatorSN(nn.Module):
    """Per-pixel real/fake logits, same spatial size as the input.
    Input height/width must be divisible by 8."""

    def __init__(self, num_feat: int = 64) -> None:
        super().__init__()
        sn = spectral_norm
        self.conv0 = nn.Conv2d(3, num_feat, 3, 1, 1)
        self.conv1 = sn(nn.Conv2d(num_feat, num_feat * 2, 4, 2, 1, bias=False))
        self.conv2 = sn(nn.Conv2d(num_feat * 2, num_feat * 4, 4, 2, 1, bias=False))
        self.conv3 = sn(nn.Conv2d(num_feat * 4, num_feat * 8, 4, 2, 1, bias=False))
        self.conv4 = sn(nn.Conv2d(num_feat * 8, num_feat * 4, 3, 1, 1, bias=False))
        self.conv5 = sn(nn.Conv2d(num_feat * 4, num_feat * 2, 3, 1, 1, bias=False))
        self.conv6 = sn(nn.Conv2d(num_feat * 2, num_feat, 3, 1, 1, bias=False))
        self.conv7 = sn(nn.Conv2d(num_feat, num_feat, 3, 1, 1, bias=False))
        self.conv8 = sn(nn.Conv2d(num_feat, num_feat, 3, 1, 1, bias=False))
        self.conv9 = nn.Conv2d(num_feat, 1, 3, 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        act = lambda t: F.leaky_relu(t, 0.2)  # noqa: E731
        up = lambda t: F.interpolate(t, scale_factor=2, mode="bilinear", align_corners=False)  # noqa: E731
        x0 = act(self.conv0(x))
        x1 = act(self.conv1(x0))
        x2 = act(self.conv2(x1))
        x3 = act(self.conv3(x2))
        x4 = act(self.conv4(up(x3))) + x2
        x5 = act(self.conv5(up(x4))) + x1
        x6 = act(self.conv6(up(x5))) + x0
        out = act(self.conv7(x6))
        out = act(self.conv8(out))
        return self.conv9(out)
