# -*- coding: UTF-8 -*-
# This file is part of the jetson_stats package (https://github.com/rbonghi/jetson_stats or http://rnext.it).
# Copyright (c) 2019 Raffaello Bonghi.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import re
from threading import Thread
# Logging
import logging
# Launch command
import subprocess as sp
# Import exceptions
from .exceptions import JtopException
# Create logger
logger = logging.getLogger(__name__)
# Regular expressions
REGEXP = re.compile(r'POWER_MODEL: ID=(.+?) NAME=((.*))')
REGPM = re.compile(r'NV Power Mode: ((.*))')


def NVP_get_id(modes, value):
    try:
        mode_id = modes.index(value)
    except ValueError:
        raise JtopException("This mode {value} does not exists".format(value=value))
    return mode_id


class NVPModel(object):
    """
        This controller read the status from your NVIDIA Jetson and you can control
        performance and status.
        It is available for NVIDIA Jetson TX2, Jetson AGX Xavier, Jetson Nano
        Boards reference:
        * TX2: https://www.jetsonhacks.com/2017/03/25/nvpmodel-nvidia-jetson-tx2-development-kit/
        * AGX Xavier: https://www.jetsonhacks.com/2018/10/07/nvpmodel-nvidia-jetson-agx-xavier-developer-kit/
        * Nano: https://www.jetsonhacks.com/2019/04/10/jetson-nano-use-more-power/
    """
    def __init__(self):
        self._nvpm = {}
        # Initialize mode
        self._mode = ""

    @property
    def status(self):
        return [self._nvpm[k]['status'] for k in sorted(self._nvpm)]

    @property
    def modes(self):
        # Make sorted list
        return [self._nvpm[k]['name'] for k in sorted(self._nvpm)]

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._mode

    def set(self, value):
        if isinstance(value, str):
            # Convert MODE to ID
            mode_id = NVP_get_id(self.modes, value)
        elif isinstance(value, int):
            # Check if ID is in list
            if value < 0 or value > len(self.modes):
                raise JtopException("This ID {value} does not exists".format(value=value))
            mode_id = value
        else:
            raise TypeError("Data type not allowed {type}".format(type=type(value)))
        return mode_id

    def __add__(self, number):
        # TODO: Implement
        pass

    def __sub__(self, number):
        # TODO: Implement
        pass

    def __iadd__(self, number):
        # Get new number
        return self._id + number

    def __isub__(self, number):
        # Get new number
        return self._id - number

    def __repr__(self):
        return self._mode

    def _update(self, mode, modes):
        # Update nvpm modes
        self._nvpm = modes['modes']
        if not modes['ser']:
            self._mode = mode
        self._id = NVP_get_id(self.modes, self._mode)


class NVPModelService(object):

    def __init__(self, jetson_clocks, nvp_model):
        self.nvpmodel_name = nvp_model
        # Initialize thread
        self._thread = None
        # Initialize jetson_clocks config
        self.jetson_clocks = jetson_clocks
        # Read all lines and extract modes
        self._nvpm = {}
        try:
            nvpmodel_p = sp.Popen([nvp_model, '-p', '--verbose'], stdout=sp.PIPE)
            out, _ = nvpmodel_p.communicate()
            # Decode lines
            lines = out.decode("utf-8")
            for line in lines.split("\n"):
                # Search configuration NVPmodel
                match = REGEXP.search(line)
                # if match extract name and number
                if match:
                    # Extract id and name
                    mode_id = int(match.group(1))
                    mode_name = str(match.group(2))
                    # Save in nvpm list
                    self._nvpm[mode_id] = {'name': mode_name, 'status': True}
        except OSError:
            logger.warning("This board does not have NVP Model")
            raise JtopException("NVPmodel does not exist for this board")

    def _thread_set_nvp_model(self, value):
        if self.jetson_clocks is None:
            # Set NV Power Mode
            return self._mode(value)
        # Otherwise disable the jetson_clocks
        old_status = self.jetson_clocks.is_alive
        if old_status:
            self.jetson_clocks.stop()
            # Check jetson_clocks is off
            while self.jetson_clocks.is_alive:
                pass
            logger.info("NVPmodel switch off jetson_clocks")
        # Set NV Power Mode
        status = self._mode(value)
        # Update status
        self._nvpm[value]['status'] = status
        # Enable again the jetson_clocks status
        if old_status:
            self.jetson_clocks.start()
            # Check jetson_clocks is off
            while not self.jetson_clocks.is_alive:
                pass
            logger.info("NVPmodel - Jetson Clocks status {status}".format(status=self.jetson_clocks.is_alive))
        logger.info("NVPmodel started {value}".format(value=value))

    def is_running(self):
        if self._thread is None:
            return False
        return self._thread.isAlive()

    def set(self, value):
        if self.is_running():
            return False
        # Start thread Service client
        self._thread = Thread(target=self._thread_set_nvp_model, args=(value, ))
        # self._thread.daemon = True
        self._thread.start()
        return True

    def modes(self):
        return self._nvpm

    def _mode(self, level):
        """ Set nvpmodel to a new status """
        self.selected = level
        # Set the new nvpmodel status
        sep_nvp = sp.Popen([self.nvpmodel_name, '-m', str(level)], stdout=sp.PIPE, stderr=sp.PIPE, stdin=sp.PIPE)
        out, _ = sep_nvp.communicate()
        # If there are no errors return the NV Power mode
        return "NVPM ERROR" not in out.decode("utf-8")

    def get(self):
        # Initialize mode and num
        _, mode = NVPModelService.query(self.nvpmodel_name)
        # Return the mode
        return mode

    @staticmethod
    def query(nvp_model):
        """ Read nvpmodel to know the status of the board """
        num = -1
        mode = ""
        nvpmodel_p = sp.Popen([nvp_model, '-q'], stdout=sp.PIPE, stderr=sp.PIPE)
        out, _ = nvpmodel_p.communicate()
        # Decode lines and split
        lines = out.decode("utf-8").split("\n")
        # Extract lines
        for idx, line in enumerate(lines):
            # Search configuration NVPmodel
            match = REGPM.search(line)
            # if match extract name and number
            if match:
                # Extract NV Power Mode
                mode = str(match.group(1))
                # Extract number
                num = int(lines[idx + 1])
                break
        return num, mode
# EOF
