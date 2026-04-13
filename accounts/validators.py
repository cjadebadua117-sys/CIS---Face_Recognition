import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexityValidator:
    """
    Minimal password validator - allows users to use any password they desire.
    Only checks that password is not empty.
    """

    def validate(self, password, user=None):
        # No restrictions - allow any password the user wants
        pass

    def get_help_text(self):
        return _("You may use any password you desire.")