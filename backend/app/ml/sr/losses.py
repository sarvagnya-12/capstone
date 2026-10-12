"""VGG19 perceptual loss for ESRGAN training.

Compares images in the feature space of an ImageNet-trained VGG19 rather than
pixel by pixel, so the generator is rewarded for plausible texture instead of
the blurry average a pure L1 loss converges to. Features are taken BEFORE the
ReLU (ESRGAN's finding: post-activation features are sparse and give weaker,
brightness-shifted supervision).

These pretrained weights are used only inside the training loss. They are
never part of the shipped upscaler, which is trained from random
initialisation on the shoe corpus.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn

# Index of each conv layer in torchvision's vgg19().features, and its weight
# (Real-ESRGAN's defaults: deep layers dominate, shallow ones lightly).
_LAYER_WEIGHTS = {2: 0.1, 7: 0.1, 16: 1.0, 25: 1.0, 34: 1.0}  # conv1_2, conv2_2, conv3_4, conv4_4, conv5_4
_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD = (0.229, 0.224, 0.225)


class VGGPerceptualLoss(nn.Module):
    def __init__(self, features: nn.Sequential | None = None) -> None:
        super().__init__()
        if features is None:
            from torchvision.models import VGG19_Weights, vgg19

            features = vgg19(weights=VGG19_Weights.IMAGENET1K_V1).features
        last = max(_LAYER_WEIGHTS)
        layers = list(features.children())[: last + 1]
        for layer in layers:
            # In-place ReLU would overwrite the pre-activation tensors we keep.
            if isinstance(layer, nn.ReLU):
                layer.inplace = False
        self.features = nn.Sequential(*layers).eval()
        for p in self.features.parameters():
            p.requires_grad_(False)
        self.register_buffer("mean", torch.tensor(_IMAGENET_MEAN).view(1, 3, 1, 1))
        self.register_buffer("std", torch.tensor(_IMAGENET_STD).view(1, 3, 1, 1))

    def _feats(self, x: torch.Tensor) -> dict[int, torch.Tensor]:
        x = (x - self.mean) / self.std
        out = {}
        for i, layer in enumerate(self.features):
            x = layer(x)
            if i in _LAYER_WEIGHTS:
                out[i] = x
        return out

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_f = self._feats(pred)
        with torch.no_grad():
            target_f = self._feats(target)
        return sum(w * F.l1_loss(pred_f[i], target_f[i]) for i, w in _LAYER_WEIGHTS.items())
