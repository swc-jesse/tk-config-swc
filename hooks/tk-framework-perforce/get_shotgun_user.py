"""
Hook that gets called to return the Shotgun user for a specified Perforce user
"""

import sgtk
import os
import sys


class GetShotgunUser(sgtk.Hook):

    def execute(self, p4_user, **kwargs):
        """
        Return the Shotgun user dictionary for the specified Perforce user

        :param p4_user:  String
                         The Perforce user name

        :returns:        Dictionary
                         The Shotgun user dictionary for the specified Perforce user
        """

        if not p4_user:
            # can't determine Shotgun user if we don't know p4 user!
            return None

        # default implementation assumes the perforce user name matches the users login:
        sg_res = self.parent.shotgun.find_one('HumanUser',
                                              [['sg_p4_user', 'is', p4_user]],
                                              ["id", "type", "email", "login", "name", "image"])
        return sg_res
