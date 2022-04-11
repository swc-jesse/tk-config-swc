# Copyright (c) 2015 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type.
"""

import glob
import os
import re
import sgtk

from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()


class HoudiniOverrideActions(HookBaseClass):
 ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things

    def _merge(self, path, sg_publish_data):
        """
        Merge a published hip file into the working hip file with
        the default settings Houdini would use if you did it in the UI.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        import hou

        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)

        # use the default settings, which tries to merge all nodes
        # and is conservative about overwriting and errors
        #
        # NOTE: We're ensuring that the path uses forward-slash separators
        # since some hearly H17 builds had major issues with backslashes on
        # Windows.
        hou.hipFile.merge(
            path.replace(os.path.sep, "/"),
            node_pattern="*",
            overwrite_on_conflict=False,
            ignore_load_warnings=False,
        )

    ##############################################################################################################
    def _import(self, path, sg_publish_data):
        """Import the supplied path as a geo/alembic sop.

        :param str path: The path to the file to import.
        :param dict sg_publish_data: The publish data for the supplied path.

        """

        import hou

        app = self.parent

        name = sg_publish_data.get("name", "alembic")
        path = self.get_publish_path(sg_publish_data)

        # houdini doesn't like UNC paths.
        path = path.replace("\\", "/")

        obj_context = _get_current_context("/obj")

        try:
            geo_node = obj_context.createNode("geo", name)
        except hou.OperationFailed:
            # failed to create the node in this context, create at top-level
            obj_context = hou.node("/obj")
            geo_node = obj_context.createNode("geo", name)

        app.log_debug("Created geo node: %s" % (geo_node.path(),))

        # delete the default nodes created in the geo
        for child in geo_node.children():
            child.destroy()

        alembic_sop = geo_node.createNode("alembic", name)
        alembic_sop.parm("fileName").set(path)
        app.log_debug(
            "Creating alembic sop: %s\n  path: '%s' " % (alembic_sop.path(), path)
        )
        alembic_sop.parm("reload").pressButton()

        _show_node(alembic_sop)

    ##############################################################################################################
    def _file_cop(self, path, sg_publish_data):
        """Read the supplied path as a file COP.

        :param str path: The path to the file to import.
        :param dict sg_publish_data: The publish data for the supplied path.

        """

        import hou

        app = self.parent

        publish_name = sg_publish_data.get("name", "published_file")

        # we'll use the publish name for the file cop node name, but we need to
        # remove non alphanumeric characers from the string (houdini node names
        # must be alphanumeric). first, build a regex to match non alpha-numeric
        # characters. Then use it to replace any matches with an underscore

        # cannot use special characters to create nodes
        pattern = re.compile("[\W_]+")
        publish_name = pattern.sub("_", publish_name)

        # get the publish path
        path = self.get_publish_path(sg_publish_data)

        # houdini doesn't like UNC paths.
        path = path.replace("\\", "/")

        img_context = _get_current_context("/img")

        try:
            file_cop = img_context.createNode("file", publish_name)
        except hou.OperationFailed:
            # failed to create the node in the current context.
            img_context = hou.node("/img")

            comps = [c for c in img_context.children() if c.type().name() == "img"]

            if comps:
                # if there are comp networks, just pick the first one
                img_network = comps[0]
            else:
                # if not, create one at the /img and then add the file cop
                img_network = img_context.createNode("img", "comp1")

            file_cop = img_network.createNode("file", publish_name)

        # replace any %0#d format string with the corresponding houdini frame
        # env variable. example %04d => $F4
        frame_pattern = re.compile("(%0(\d)d)")
        frame_match = re.search(frame_pattern, path)
        if frame_match:
            full_frame_spec = frame_match.group(1)
            padding = frame_match.group(2)
            path = path.replace(full_frame_spec, "$F%s" % (padding,))

        file_cop.parm("filename1").set(path)
        app.log_debug("Created file COP: %s\n  path: '%s' " % (file_cop.path(), path))
        file_cop.parm("reload").pressButton()

        _show_node(file_cop)


##############################################################################################################
def _get_current_context(context_type):
    """Attempts to return the current node context.

    :param str context_type: Return a full context under this context type.
        Example: "/obj"

    Looks for a current network pane tab displaying the supplied context type.
    Returns the full context being displayed in that network editor.

    """

    import hou

    # default to the top level context type
    context = hou.node(context_type)

    network_tab = _get_current_network_panetab(context_type)
    if network_tab:
        context = network_tab.pwd()

    return context


##############################################################################################################
def _get_current_network_panetab(context_type):
    """Attempt to retrieve the current network pane tab.

    :param str context_type: Search for a network pane showing this context
        type. Example: "/obj"

    """

    import hou

    network_tab = None

    # there doesn't seem to be a way to know the current context "type" since
    # there could be multiple network panels open with different contexts
    # displayed. so for now, loop over pane tabs and find a network editor in
    # the specified context type that is the current tab in its pane. hopefully
    # that's the one the user is looking at.
    for panetab in hou.ui.paneTabs():
        if (
            isinstance(panetab, hou.NetworkEditor)
            and panetab.pwd().path().startswith(context_type)
            and panetab.isCurrentTab()
        ):

            network_tab = panetab
            break

    return network_tab


##############################################################################################################
def _show_node(node):
    """Frame the supplied node in the current network pane.

    :param hou.Node node: The node to frame in the current network pane.

    """

    context_type = "/" + node.path().split("/")[0]
    network_tab = _get_current_network_panetab(context_type)

    if not network_tab:
        return

    # select the node and frame it
    node.setSelected(True, clear_all_selected=True)
    network_tab.cd(node.parent().path())
    network_tab.frameSelection()