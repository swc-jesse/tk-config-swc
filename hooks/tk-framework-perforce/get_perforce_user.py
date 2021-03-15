"""
Hook that gets called to return the current Perforce user for a
specified Shotgun user
"""

import sgtk
import os
import sys


class GetPerforceUser(sgtk.Hook):

    def execute(self, sg_user, **kwargs):
        """
        Return the Perforce username associated with the specified shotgun user

        :param sg_user:  Dictionary
                         The shotgun user entity fields

        :returns:        String
                         The Perforce username for the specified Shotgun user
        """

        if not sg_user:
            # can't determine Perforce user if we don't know sg user!
            return None

        # default implementation just uses the users login:
        if "sg_p4_user" in sg_user:
            return sg_user["sg_p4_user"]

        sg_res = self.parent.shotgun.find_one("HumanUser", [["id", "is", sg_user["id"]]], ["sg_p4_user"])
        if sg_res:
            return sg_res.get("sg_p4_user")
