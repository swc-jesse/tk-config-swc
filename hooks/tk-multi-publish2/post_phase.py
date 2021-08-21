# Copyright (c) 2018 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pprint

import sgtk

HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_PERFORCE_NAME = "tk-framework-perforce_v0.x.x"


class PostPhaseHook(HookBaseClass):
    """
    This hook defines methods that are executed after each phase of a publish:
    validation, publish, and finalization. Each method receives the publish
    tree instance being used by the publisher, giving full control to further
    curate the publish tree including the publish items and the tasks attached
    to them. See the :class:`PublishTree` documentation for additional details
    on how to traverse the tree and manipulate it.
    """

    def post_publish(self, publish_tree):

        self.logger.debug("Starting Post-publish phase.")
        publisher = self.parent

        # Make the p4 connection
        self.p4_fw = self.load_framework(TK_FRAMEWORK_PERFORCE_NAME)
        self.logger.debug("Perforce framework loaded.")

        p4 = self.p4_fw.connection.connect()
        self.logger.debug("Perforce connection made.")

        # create a new changelist for all files being published:
        self.logger.info("Creating new Perforce changelist...")
        new_change = self.p4_fw.util.create_change(p4, "Shotgun publish")
        # NOTE: new_change just returns the id of the change

        change_items = []

        for item in publish_tree:

            if item.properties.get('publish_data'):

                path = item.properties.get("path")

                self.logger.info("Ensuring file is checked out...")
                self.p4_fw.util.open_file_for_edit(p4, path, add_if_new=True)

                # depo_paths = self.p4_fw.util.client_to_depot_paths(p4, path)
                # self.logger.info("Depo paths: {}".format(depo_paths))
                # NOTE: This returns an empty string for new files. Presumably
                # this function only works for files already in the depo.

                # and add the file to this change:
                self.logger.info("Adding the file to the change: {}".format(path))
                self.p4_fw.util.add_to_change(p4, new_change, path)
                # NOTE: for some reason this is not adding anything to the change
                # and I cannot figure out why.

                change_items.append(item)

        for result in p4.run('files', '@=' + new_change):
            # NOTE: well this shit doesnt work at all.

            self.logger.debug(
                "Perforce Change details...",
                extra={
                    "action_show_more_info": {
                        "label": "P4 Change details",
                        "tooltip": "Show the Perforce Change details before check-in",
                        "text": "<pre>%s</pre>".format(pprint.pformat(result)),
                    }
                },
            )

        # submit the change:
        self.logger.info("Submitting the change...")
        submission = self.p4_fw.util.submit_change(p4, new_change)

        self.logger.debug(
            "Perforce Submission data...",
            extra={
                "action_show_more_info": {
                    "label": "P4 Submission",
                    "tooltip": "Show the complete Perforce Submission data",
                    "text": "<pre>{}</pre>".format(pprint.pformat(submission)),
                }
            },
        )

        changed_files = [i for i in [s for s in submission if isinstance(s, dict)] if i.get('depotFile')]
        """
        [{'action': 'edit',
          'depotFile': '//deva/Tool/ScorchedEarth/ToolCategory/ToolTestAsset/deva_ScorchedEarth_ToolTestAsset_concept.psd',
          'rev': '4'},
         {'action': 'edit',
          'depotFile': '//deva/Tool/ScorchedEarth/ToolCategory/ToolTestAsset/deva_ScorchedEarth_ToolTestAsset_concept_alt.psd',
          'rev': '6'}]
        """

        submitted_change = next((int(i['submittedChange']) for i in [s for s in submission if isinstance(s, dict)] if i.get('submittedChange')), None)
        """
        {'submittedChange': '92'}
        """

        for item in change_items:

            # TODO: iterate thru the submission and update each items publish_data with
            # the perforce data (version_number, sg_p4_change_number, sg_p4_depo_path)

            depot_path = self.p4_fw.util.client_to_depot_paths(p4, item.properties.get("path"))[0]
            self.logger.debug("depot_path = {}".format(depot_path))
            change_data = next(i for i in changed_files if i['depotFile'] == depot_path)

            if change_data:

                # use the p4 revision number as the version number
                item.properties.publish_data["version_number"] = int(change_data["rev"])

                # attach the p4 data to the "sg_fields" dict which updates the published file entry in SG
                item.properties.publish_data["sg_fields"]["sg_p4_depo_path"] = change_data["depotFile"]
                item.properties.publish_data["sg_fields"]["sg_p4_change_number"] = submitted_change

                item.properties.sg_publish_data = sgtk.util.register_publish(**item.properties.publish_data)

                # update the published file 'code' field to match Perforce rev formating (filename.ext#rev) so we can tell them apart in SG
                update_data = {'code': "{}#{}".format(item.properties.sg_publish_data['code'], change_data["rev"])}
                publisher.shotgun.update("PublishedFile", item.properties.sg_publish_data['id'], update_data)   

                self.logger.info("Publish registered!")
                self.logger.debug(
                    "ShotGrid Publish data...",
                    extra={
                        "action_show_more_info": {
                            "label": "ShotGrid Publish Data",
                            "tooltip": "Show the complete ShotGrid Publish Entity dictionary",
                            "text": "<pre>{}</pre>".format(pprint.pformat(item.properties.sg_publish_data)),
                        }
                    },
                )
