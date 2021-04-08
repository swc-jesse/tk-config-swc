# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pymxs

import sgtk
from sgtk import TankError

HookClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the current scene
    """

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
        p4_fw.util = p4_fw.import_module("util")

        if operation == "current_path":
            # return the current scene path or an empty string.
            return _session_path() or ""

        elif operation == "open":
            # check that we have the correct version synced:
            p4 = p4_fw.connection.connect()
            if not read_only:
                # open the file for edit:
                p4_fw.util.open_file_for_edit(p4, file_path, add_if_new=False)

            # open the specified scene
            _open_file(file_path)

        elif operation == "save":
            # save the current scene:
            _save_file()

        elif operation == "save_as":
            # ensure the file is checked out if it's a Perforce file:
            try:
                p4 = p4_fw.connection.connect()
                p4_fw.util.open_file_for_edit(p4, file_path, add_if_new=False)
            except TankError, e:
                self.parent.log_warning(e)

            # save the scene as file_path:
            _save_file(file_path)

        elif operation == "reset":
            """
            Reset the scene to an empty state
            """
            _reset_scene()
            return True


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    if pymxs.runtime.maxFilePath and pymxs.runtime.maxFileName:
        return os.path.join(pymxs.runtime.maxFilePath, pymxs.runtime.maxFileName)
    else:
        return None


def _open_file(file_path):
    pymxs.runtime.loadMaxFile(file_path)


def _save_file(file_path=None):
    if file_path is None:
        pymxs.runtime.execute("max file saveas")
    else:
        pymxs.runtime.saveMaxFile(file_path)


def _reset_scene():
    pymxs.runtime.resetMaxFile(pymxs.runtime.Name("noprompt"))
