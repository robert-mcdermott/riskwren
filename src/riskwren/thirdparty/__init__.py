"""Third parties as a program (TPR): what each provides, how much is at stake with it, what it
says about itself and what others report of it, and whether an agreement covers what is shared.

Importing the package registers services as a record type and gives third parties what this
wave adds to them.
"""

from riskwren.thirdparty import (  # noqa: F401  (registers them)
    assurance,
    coverage,
    profile,
    reviews,
    services,
    tiering,
)

coverage.install()  # after profile and services, whose detail it adds to
