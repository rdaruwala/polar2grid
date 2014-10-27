#!/usr/bin/env python
# encoding: utf-8
# Copyright (C) 2014 Space Science and Engineering Center (SSEC),
# University of Wisconsin-Madison.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file is part of the polar2grid software package. Polar2grid takes
# satellite observation data, remaps it, and writes it to a file format for
#     input into another program.
# Documentation: http://www.ssec.wisc.edu/software/polar2grid/
#
# Written by David Hoese    October 2014
# University of Wisconsin-Madison
# Space Science and Engineering Center
# 1225 West Dayton Street
# Madison, WI  53706
# david.hoese@ssec.wisc.edu
"""Connect various polar2grid components together to go from satellite data to output imagery format.

:author:       David Hoese (davidh)
:author:       Ray Garcia (rayg)
:contact:      david.hoese@ssec.wisc.edu
:organization: Space Science and Engineering Center (SSEC)
:copyright:    Copyright (c) 2014 University of Wisconsin SSEC. All rights reserved.
:date:         Jan 2014
:license:      GNU GPLv3

"""
__docformat__ = "restructuredtext en"

import pkg_resources
from polar2grid.remap import Remapper, add_remap_argument_groups

import sys
import logging

### Return Status Values ###
STATUS_SUCCESS       = 0
# the frontend failed
STATUS_FRONTEND_FAIL = 1
# the backend failed
STATUS_BACKEND_FAIL  = 2
# either ll2cr or fornav failed (4 + 8)
STATUS_REMAP_FAIL    = 12
# ll2cr failed
STATUS_LL2CR_FAIL    = 4
# fornav failed
STATUS_FORNAV_FAIL   = 8
# grid determination or grid jobs creation failed
STATUS_GDETER_FAIL   = 16
# not sure why we failed, not an expected failure
STATUS_UNKNOWN_FAIL  = -1

P2G_FRONTEND_CLS_EP = "polar2grid.frontend_class"
P2G_FRONTEND_ARGS_EP = "polar2grid.frontend_arguments"
P2G_BACKEND_CLS_EP = "polar2grid.backend_class"
P2G_BACKEND_ARGS_EP = "polar2grid.backend_arguments"

FRONTENDS = {frontend_ep.name: frontend_ep.dist for frontend_ep in pkg_resources.iter_entry_points(P2G_FRONTEND_CLS_EP)}
BACKENDS = {backend_ep.name: backend_ep.dist for backend_ep in pkg_resources.iter_entry_points(P2G_BACKEND_CLS_EP)}


def get_frontend_argument_func(name):
    return pkg_resources.load_entry_point(FRONTENDS[name], P2G_FRONTEND_ARGS_EP, name)


def get_frontend_class(name):
    return pkg_resources.load_entry_point(FRONTENDS[name], P2G_FRONTEND_CLS_EP, name)


def get_backend_argument_func(name):
    return pkg_resources.load_entry_point(BACKENDS[name], P2G_BACKEND_ARGS_EP, name)


def get_backend_class(name):
    return pkg_resources.load_entry_point(BACKENDS[name], P2G_BACKEND_CLS_EP, name)


def main(argv=sys.argv[1:]):
    # from argparse import ArgumentParser
    # init_parser = ArgumentParser(description="Extract swath data, remap it, and write it to a new file format")
    from polar2grid.core.script_utils import setup_logging, create_basic_parser, create_exc_handler, rename_log_file, ExtendAction
    from argparse import ArgumentError
    parser = create_basic_parser(description="Extract swath data, remap it, and write it to a new file format")
    parser.add_argument("frontend", choices=sorted(FRONTENDS.keys()),
                        help="Specify the swath extractor to use to read data (additional arguments are determined after this is specified)")
    parser.add_argument("backend", choices=sorted(BACKENDS.keys()),
                        help="Specify the backend to use to write data output (additional arguments are determined after this is specified)")
    # don't include the help flag
    argv_without_help = [x for x in argv if x not in ["-h", "--help"]]
    args, remaining_args = parser.parse_known_args(argv_without_help)
    glue_name = args.frontend + "2" + args.backend
    LOG = logging.getLogger(glue_name)

    # load the actual components we need
    farg_func = get_frontend_argument_func(args.frontend)
    fcls = get_frontend_class(args.frontend)
    barg_func = get_backend_argument_func(args.backend)
    bcls = get_backend_class(args.backend)

    # add_frontend_arguments(parser)
    group_titles = []
    group_titles += farg_func(parser)
    group_titles += add_remap_argument_groups(parser)
    group_titles += barg_func(parser)
    parser.add_argument('-f', dest='data_files', nargs="+", default=[], action=ExtendAction,
                        help="List of files or directories to extract data from")
    parser.add_argument('-d', dest='data_files', nargs="+", default=[], action=ExtendAction,
                        help="Data directories to look for input data files (equivalent to -f)")
    parser.add_argument('--ignore-error', dest="exit_on_error", action="store_false",
                        help="if a non-fatal error is encountered ignore it and continue for the remaining products")
    global_keywords = ("keep_intermediate", "overwrite_existing", "exit_on_error")
    args = parser.parse_args(argv, global_keywords=global_keywords, subgroup_titles=group_titles)

    if not args.data_files:
        # FUTURE: When the -d flag is removed this won't be needed because -f will be required
        parser.print_usage()
        parser.exit(1, "ERROR: No data files provided (-f flag)\n")

    # Logs are renamed once data the provided start date is known
    rename_log = False
    if args.log_fn is None:
        rename_log = True
        args.log_fn = glue_name + "_fail.log"
    levels = [logging.ERROR, logging.WARN, logging.INFO, logging.DEBUG]
    setup_logging(console_level=levels[min(3, args.verbosity)], log_filename=args.log_fn)
    sys.excepthook = create_exc_handler(LOG.name)
    LOG.debug("Starting script with arguments: %s", " ".join(sys.argv))

    # Keep track of things going wrong to tell the user what went wrong (we want to create as much as possible)
    status_to_return = STATUS_SUCCESS

    # Frontend
    try:
        LOG.info("Initializing swath extractor...")
        list_products = args.subgroup_args["Frontend Initialization"].pop("list_products")
        f = fcls(args.data_files, **args.subgroup_args["Frontend Initialization"])
    except StandardError:
        LOG.debug("Frontend exception: ", exc_info=True)
        LOG.error("%s frontend failed to load and sort data files (see log for details)", args.frontend)
        return STATUS_FRONTEND_FAIL

    # Rename the log file
    if rename_log:
        rename_log_file(glue_name + f.begin_time.strftime("_%Y%m%d_%H%M%S.log"))

    if list_products:
        print("\n".join(f.available_product_names))
        return STATUS_SUCCESS

    try:
        LOG.info("Initializing remapping...")
        remapper = Remapper(**args.subgroup_args["Remapping Initialization"])
        remap_kwargs = args.subgroup_args["Remapping"]
    except StandardError:
        LOG.debug("Remapping initialization exception: ", exc_info=True)
        LOG.error("Remapping initialization failed (see log for details)")
        return STATUS_REMAP_FAIL

    try:
        LOG.info("Initializing backend...")
        backend = bcls(**args.subgroup_args["Backend Initialization"])
    except StandardError:
        LOG.debug("Backend initialization exception: ", exc_info=True)
        LOG.error("Backend initialization failed (see log for details)")
        return STATUS_BACKEND_FAIL

    try:
        LOG.info("Extracting swaths from data files available...")
        scene = f.create_scene(**args.subgroup_args["Frontend Swath Extraction"])
        if args.keep_intermediate:
            scene.save(glue_name + "_swath_scene.json")
    except StandardError:
        LOG.debug("Frontend data extraction exception: ", exc_info=True)
        LOG.error("Frontend data extraction failed (see log for details)")
        return STATUS_FRONTEND_FAIL

    # Remap
    gridded_scenes = {}
    # TODO: Grid determination
    for grid_name in remap_kwargs.pop("forced_grids"):
        try:
            LOG.info("Remapping to grid %s", grid_name)
            gridded_scene = remapper.remap_scene(scene, grid_name, **remap_kwargs)
            gridded_scenes[grid_name] = gridded_scene
            if args.keep_intermediate:
                gridded_scene.save(glue_name + "_gridded_scene_" + grid_name + ".json")
        except StandardError:
            LOG.debug("Remapping data exception: ", exc_info=True)
            LOG.error("Remapping data failed")
            status_to_return |= STATUS_REMAP_FAIL
            if args.exit_on_error:
                raise
            continue

        # Backend
        try:
            LOG.info("Creating output from data mapped to grid %s", grid_name)
            backend.create_output_from_scene(gridded_scene, **args.subgroup_args["Backend Output Creation"])
        except StandardError:
            LOG.debug("Backend output creation exception: ", exc_info=True)
            LOG.error("Backend output creation failed (see log for details)")
            status_to_return |= STATUS_BACKEND_FAIL
            if args.exit_on_error:
                raise
            continue

    return status_to_return

if __name__ == "__main__":
    sys.exit(main())