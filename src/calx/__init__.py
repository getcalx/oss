"""getcalx is deprecated. Calx has moved to a cloud-hosted model. Visit https://calx.sh for setup."""

import warnings

__version__ = "0.8.0"

_DEPRECATION_MESSAGE = (
    "getcalx is deprecated. Calx has moved to a cloud-hosted model. "
    "Visit https://calx.sh for the new setup. "
    "This package will receive no further updates."
)

warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
