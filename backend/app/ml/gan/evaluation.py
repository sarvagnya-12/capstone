"""FID (Frechet Inception Distance) computation for generated product
variants.

Closes Open Decision #5's realism-metric gap (previously undocumented
anywhere in the source material). FID is fundamentally a set-vs-set
statistic: it fits a Gaussian to InceptionV3 features of a "real" image set
and a "fake" image set, then measures the Frechet distance between the two
Gaussians. Until ref_images has real per-category product photos to compare
against (Step 13's dataset pipeline currently has zero real records), the
only available "real" set is a single product's own 1-2 reference images
(original + preprocessed) against a handful of generated variants. That is a
genuinely small-sample, rough signal -- not a statistically rigorous
benchmark. Stated here explicitly per this step's own completion criteria,
and carried into Section 8 (Testing Plan) as a known caveat, not silently
hidden.

FID is a set-level statistic, not a per-image one: all variants generated in
the same batch share one fid_score (the batch compared as a whole against
the real set), rather than each variant getting an independently-computed
score -- there is no meaningful way to compute FID for a single image.
"""

from typing import Optional

import torch
from torchmetrics.image.fid import FrechetInceptionDistance


def compute_fid(real_images: list[torch.Tensor], fake_images: list[torch.Tensor]) -> Optional[float]:
    """real_images/fake_images: each a (3, H, W) float tensor in [0, 1] (the
    same format app.ml.gan.model's generate_image() functions return).
    Returns None -- not a misleading NaN/Inf number -- if the sample is too
    degenerate for FID's covariance estimation to produce a finite result."""
    if len(real_images) < 2 or len(fake_images) < 2:
        return None  # FID's covariance estimate is undefined below n=2

    fid = FrechetInceptionDistance(feature=2048, normalize=True)
    fid.update(torch.stack(real_images), real=True)
    fid.update(torch.stack(fake_images), real=False)

    try:
        score = fid.compute().item()
    except Exception:
        return None

    return score if torch.isfinite(torch.tensor(score)) else None
