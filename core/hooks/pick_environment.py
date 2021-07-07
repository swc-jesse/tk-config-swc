# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which chooses an environment file to use based on the current context.
"""

import sgtk

logger = sgtk.platform.get_logger(__name__)


class PickEnvironment(sgtk.Hook):
    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are three environments, called shot, asset
        and project, and switches to these based on entity type.
        """

        if context.source_entity:
            if context.source_entity["type"] == "Version":
                return "version"
            elif context.source_entity["type"] == "PublishedFile":
                return "publishedfile"

        if context.project is None:
            # Our context is completely empty. We're going into the site context.
            return "site"

        if context.entity is None:
            # We have a project but not an entity.
            return "project"

        if context.entity and context.step is None:
            # We have an entity but no step.
            if context.entity["type"] == "Asset":
                context_entity = context.sgtk.shotgun.find_one("Asset",
                                                               [["id", "is", context.entity["id"]]],
                                                               ["sg_asset_parent","sg_asset_type","project"])
                context_project = context.sgtk.shotgun.find_one("Project",
                                                               [["id", "is", context_entity.get('project')["id"]]],
                                                               ["sg_non_game_asset_types"])
                asset_env = "asset"

                assets_other = []
                for x in context_project.get('sg_non_game_asset_types'): assets_other.append(x['name'])

                if context_entity.get("sg_asset_type") in assets_other:
                    asset_env = "asset_other"

                if context_entity.get("sg_asset_parent"):
                    return asset_env + "_child"

                return asset_env

        if context.entity and context.step:
            # We have a step and an entity.
            if context.entity["type"] == "Asset":
                context_entity = context.sgtk.shotgun.find_one("Asset",
                                                               [["id", "is", context.entity["id"]]],
                                                               ["sg_asset_parent","sg_asset_type"])
                context_project = context.sgtk.shotgun.find_one("Project",
                                                               [["id", "is", context_entity.get('project')["id"]]],
                                                               ["sg_non_game_asset_types"])
                asset_env = "asset"

                assets_other = []
                for x in context_project.get('sg_non_game_asset_types'): assets_other.append(x['name'])                                                               

                asset_env = "asset"
                if context_entity.get("sg_asset_type") in assets_other:
                    asset_env = "asset_other"

                if context_entity.get("sg_asset_parent"):
                    return asset_env + "_child_step"

                return asset_env + "_step"

        return None
