# This hook can be used as a base class for other scene operations that need
# perforce actions.
import os

import sgtk
from sgtk import TankError, LogManager
from sgtk.platform.qt import QtGui, QtCore

log = LogManager.get_logger(__name__)
HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"


class SceneOperation(HookBaseClass):
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
        return True
        p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
        p4_fw.util = p4_fw.import_module("connection")
        p4 = p4_fw.connection.connect()
        p4_fw.util = p4_fw.import_module("util")
        p4_icon = os.path.join(self.disk_location, os.pardir, os.pardir, "icons", "perforce.png")

        if operation == "open":
            # check if the file is checked out
            file_details = None
            try:
                file_details = p4_fw.util.get_client_file_details(p4, file_path, fields=["action"], flags=[])[file_path]
                log.debug("file_details: {}".format(file_details))
            except TankError as e:
                self.parent.log_warning(e)
            # check if the file is checked out
            if not file_details.get("action") == "edit":
                # if its not checked out, ask before opening
                msgBox = QtGui.QMessageBox()
                msgBox.setText("This file is not checked out.")
                msgBox.setInformativeText("Do you want to check it out before opening in order to make changes?")
                msgBox.setIconPixmap(QtGui.QPixmap(p4_icon).scaledToWidth(48, QtCore.Qt.SmoothTransformation))
                msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                msgBox.setDefaultButton(QtGui.QMessageBox.Yes)
                msgBox.setEscapeButton(QtGui.QMessageBox.No)

                ret = msgBox.exec_()

                if ret == QtGui.QMessageBox.Yes:
                    # check out the file
                    try:
                        p4_fw.util.open_file_for_edit(p4, file_path, add_if_new=False)
                    except TankError as e:
                        self.parent.log_warning(e)
            # operation completed successfully
            return True

        elif operation == "save_as":

            # a file exists in that path, lets make sure the user wants to overwrite it
            if os.path.exists(file_path):
                msgBox = QtGui.QMessageBox()
                msgBox.setText("This file already exists.")
                msgBox.setInformativeText("Are you sure you want to overwite this file?")
                msgBox.setIcon(QtGui.QMessageBox.Warning)
                msgBox.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
                msgBox.setDefaultButton(QtGui.QMessageBox.Yes)
                msgBox.setEscapeButton(QtGui.QMessageBox.No)

                ret = msgBox.exec_()

                if ret == QtGui.QMessageBox.Yes:
                    # check out the file
                    try:
                        p4_fw.util.open_file_for_edit(p4, file_path, add_if_new=False)
                    except TankError as e:
                        self.parent.log_warning(e)
                    # operation completed successfully
                    return True
                else:
                    # operation didn't complete
                    return False

        # no operations were found to act upon
        return True
