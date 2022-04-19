# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Before App Launch Hook

This hook is executed prior to application launch and is useful if you need
to set environment variables or run scripts as part of the app initialization.
"""

import os
import tempfile
import tank
import sgtk

HookBaseClass = sgtk.get_hook_baseclass()

maya_env_template = """MAYA_MODULE_PATH = %PERFORCE_TOOL_PATH%\MODULES;
XBMLANGPATH = %PERFORCE_TOOL_PATH%\ICONS;
MAYA_SHELF_PATH  = %PERFORCE_TOOL_PATH%\SHELVES;
PYTHONPATH = %PERFORCE_TOOL_PATH%;%PERFORCE_TOOL_PATH%\PYTHON;"""

class BeforeAppLaunch(tank.Hook):
    """
    Hook to set up the system prior to app launch.
    """

    def execute(
        self, app_path, app_args, version, engine_name, software_entity=None, **kwargs
    ):
        """
        The execute function of the hook will be called prior to starting the required application

        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.
        :param software_entity: (dict) If set, this is the Software entity that is
            associated with this launch command.
        """

        # accessing the current context (current shot, etc)
        # can be done via the parent object
        #
        # > multi_launchapp = self.parent
        # > current_entity = multi_launchapp.context.entity

        # you can set environment variables like this:
        # os.environ["MY_SETTING"] = "foo bar"

        # Append to PYTHONPATH
    
        app_tools_path = software_entity["sg_windows_tools_path"]

        if app_tools_path:
            tools_path = os.path.abspath(os.path.join(self.sgtk.project_path, os.pardir, app_tools_path))
            sgtk.util.append_path_to_env_var("PYTHONPATH", tools_path)

            if engine_name == 'tk-maya':
                # Create and point to the desired Maya.env file
                maya_env = {
                    'dir': '',
                    'file': None,
                }

                maya_env['dir'] = os.path.join(tempfile.gettempdir(),'sgtk-maya')
                if not os.path.exists(maya_env['dir']):
                    os.makedirs(maya_env['dir'])

                maya_env['file'] = open(os.path.join(maya_env['dir'],'Maya.env'),'w')
                maya_env['file'].write(f'PERFORCE_TOOL_PATH = {tools_path}\n')
                maya_env['file'].writelines(maya_env_template)
                maya_env['file'].close()
                
                os.environ["MAYA_ENV_DIR"] = maya_env['dir']
                os.environ["MAYA_TOOLS_PATH"] = tools_path
