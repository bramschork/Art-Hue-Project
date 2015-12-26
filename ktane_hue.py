"""
File: ktane_hue.py
Purpose: Control hue lights from ktane
Author: Sven Goossens
"""
import datetime
from enum import Enum, IntEnum
import json
import logging
import os
import re
import sys
import time
from phue import Bridge

logger = None

SETTINGS = 'ktane_hue.json'

# A list with the light ids of the lamps the game should control
COLOR_LAMPS = ["light1", "light2"]

# The ip of the bridge
BRIDGE = '192.168.0.42'


def main():
    setup_logger()
    if not os.path.exists(SETTINGS):
        pass
    kt = Ktane()

    # We run from the ktane folder
    lp = KtaneLogParse('logs/ktane.log')

    """The main event loop"""
    while True:
        # Parse the log, update state of Ktane class
        lp.parse_wrap(kt)
        # (light) animation tick
        kt.tick()
        # Go to sleep. This value determines the duration of each "frame" of the the light animation
        return
        time.sleep(0.1)


class KtaneState(Enum):
    in_menu = 0
    in_game = 1
    exploding = 2
    post_mortem = 3


class KtaneAction(IntEnum):
    menu_opened = 0
    round_started = 1
    round_ended = 2
    explode = 3
    win = 4
    post_mortem = 5
    result_screen_dismissed_to_menu = 6
    strike1 = 7
    strike2 = 8
    strike3 = 9
    strike4 = 10
    strike5 = 11
    result_screen_dismissed_retry = 12
    unknown = 13


class Ktane():
    """ Class that tracks the game state and controls the lights """
    def __init__(self):
        # self.b = Bridge(BRIDGE)
        self.b = MockBridge(BRIDGE)
        self.b.connect()

        self.state = KtaneState.in_menu

        self.round_started = False
        self.pulse = 0
        self.exploded = False
        self.strikes = 0
        self.won = False

        self.color_lamps = []
        for l in self.b.lights:
            if l.name in COLOR_LAMPS:
                self.menu_mode(l)
                self.color_lamps.append(l)
            else:
                l.brightness = 40

    def tick(self):
        """The function called by our main event loop"""
        if self.exploded:
            self.explode()
        elif self.round_started:
            self.do_pulse()

    def explode(self):
        """Explosion animation. Once done, it moves to the post_portem state"""
        if self.pulse == 1:
            self.normal_transitions()

        for lamp in self.color_lamps:
            if self.pulse == 0:
                lamp.brightness = 251
                self.color_red(lamp)
            elif self.pulse == 2:
                lamp.brightness = 251
                self.color_green(lamp)
            elif self.pulse == 4:
                lamp.brightness = 10
                self.color_red(lamp)

        self.pulse += 1
        if self.pulse == 50:
            self.round_started = False
            self.exploded = False
            self.pulse = 0
            self.post_mortem()

    def do_pulse(self):
        """
        Pulses the lights while the countdown timer is running.
        The pulse counts on which the state changes are chosen to be dividable
        1, 2, 3 and 4. Might glitch slightly when the number of strikes
        increases during the animation, but self corrects once self.pulse resets
        to 0.
        """
        div = 1 + max(self.strikes, 3)

        for lamp in self.color_lamps:
            if self.pulse == 0:
                self.color_mild_orange(lamp)
            elif self.pulse == 24 / div:
                self.color_orange(lamp)

        self.pulse += 1
        if self.pulse >= 48 / div:
            self.pulse = 0

    def menu_mode(self, lamp):
        """Lamp settings during the main menu / bomb selection"""
        lamp.on = True
        lamp.brightness = 200
        self.color_warm_white(lamp)

    def post_mortem(self):
        """Lamp settings during the post mortem debriefing"""
        logger.debug("post-mortem mode")
        for lamp in self.color_lamps:
            lamp.on = True
            lamp.brightness = 200
            self.color_cool_white(lamp)

    def quick_transitions(self):
        """Set lamps to quickest transition speed (fastest color change)"""
        self.set_transition_time(0)

    def normal_transitions(self):
        """Set lamps to normal transition mode."""
        self.set_transition_time(10)

    def half_transitions(self):
        self.set_transition_time(5)

    def quarter_transitions(self):
        self.set_transition_time(2)

    def set_transition_time(self, t):
        for lamp in self.color_lamps:
            lamp.transitiontime = t

    def action(self, action):
        if action == KtaneAction.round_started:
            if not self.round_started:
                self.start_round()

        if action == KtaneAction.round_ended:
            if not self.exploded:
                self.stop_round()

        if action == KtaneAction.explode:
            if self.exploded is False:
                logger.debug("exploded")
                self.exploded = True
                self.quick_transitions()
                self.pulse = 0

        if action == KtaneAction.win:
            self.won = True

        if action == KtaneAction.result_screen_dismissed_to_menu:
            self.stop_round()

        if action == KtaneAction.result_screen_dismissed_retry:
            self.stop_round()
            self.start_round()

        if action >= KtaneAction.strike1 and action <= KtaneAction.strike5:
            new_strikes = action - KtaneAction.strike1 + 1
            if new_strikes != self.strikes:
                logger.debug("Detected strike {strike}".format(strike=new_strikes))
                self.strikes = new_strikes
                if self.strikes == 1:
                    self.half_transitions()
                if self.strikes == 2:
                    self.quarter_transitions()

    def start_round(self):
        """Reset state, start round"""
        logger.debug("start_round()")
        self.normal_transitions()
        self.exploded = False
        self.won = False
        self.strikes = 0
        self.round_started = True

    def menu_mode_all(self):
        """Set all lamps to menu mode"""
        for lamp in self.color_lamps:
            self.menu_mode(lamp)

    def stop_round(self):
        """Stop round, back to menu mode"""
        logger.debug("Stopped round")
        self.round_started = False
        self.normal_transitions()
        self.menu_mode_all()

    def color_set(self, hue, sat, l):
        l.hue = hue
        l.sat = sat

    def color_cool_white(self, l):
        self.color_set(35535, 200, l)

    def color_warm_white(self, l):
        self.color_set(30535, 0, l)

    def color_red(self, l):
        self.color_set(65535, 254, l)

    def color_magenta(self, l):
        self.color_set(55535, 254, l)

    def color_blue(self, l):
        self.color_set(47125, 200, l)

    def color_orange(self, l):
        self.color_set(13535, 254, l)

    def color_mild_orange(self, l):
        self.color_set(13535, 100, l)

    def color_green(self, l):
        self.color_set(25650, 254, l)

    def color_black(self, l):
        """Not exactly black"""
        self.color_set(47125, 0, l)


class KtaneLogParse:
    def __init__(self, fname):
        self.fname = fname
        # Correct for local timezone (log contains UTC)
        self.local_tz = time.timezone

    def parse_time_str(self, time_str):
        t = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S,%f')
        return t - datetime.timedelta(seconds=self.local_tz)

    def parse_wrap(self, kt):
        """Small wrapper around the parse function"""
        with open(self.fname, 'r') as f:
            txt = f.read()
            lines = txt.splitlines()
            self.parse_log(lines, kt)

    def parse_log(self, lines, kt):
        """Parse log (list of lines). Pass useful state updates to kt."""
        for line in lines[0:2000]:
            if '[State]' in line or '[Bomb]' in line or '[PostGameState]' in line:
                logger.info('--------> {line}'.format(line=line))
                # DEBUG 2015-12-24 18:57:49,884 [Assets.Scripts.Pacing.PaceMaker] Round start! Mission: The First Bomb Pacing Enabled: False

                r = r"[ ]*(?P<log_type>[A-Z]+) (?P<start_time>[^\[]*) \[(?P<component>State|Bomb|PostGameState)\] (?P<state_info>.*)"
                m = re.match(r, line)
                res = m.groupdict()

                t = self.parse_time_str(res['start_time'])
                now = datetime.datetime.now()

                action = self.parse_action(res['state_info'])
                logger.info(action)

                if abs(t - now) < datetime.timedelta(seconds=0.3) or True:
                    # A recent change: pass to kt
                    # logger.info("State changed to {state}".format(state=res['state_info']))
                    kt.action(action)

    def parse_action(self, state_info):
        """Called by the parser when it picks up a new log entry of interest"""
        if state_info == 'Enter GameplayState':
            return KtaneAction.round_started

        if state_info == 'OnRoundEnd()':
            return KtaneAction.round_ended

        if state_info == 'Boom':
            return KtaneAction.explode

        if state_info == "A winner is you!!":
            return KtaneAction.win

        if state_info == 'Results screen bomb binder dismissed (continue). Restarting...':
            return KtaneAction.result_screen_dismissed_to_menu

        if state_info == 'Results screen bomb binder dismissed (retry). Retrying same mission...':
            return KtaneAction.result_screen_dismissed_retry

        if "strike" in state_info:
            new_strikes = int(state_info[8])

            if new_strikes == 1:
                return KtaneAction.strike1
            if new_strikes == 2:
                return KtaneAction.strike2
            if new_strikes == 3:
                return KtaneAction.strike3
            if new_strikes == 4:
                return KtaneAction.strike4
            if new_strikes == 5:
                return KtaneAction.strike5

        return KtaneAction.unknown


def setup_logger():
    global logger
    logger = logging.getLogger('ktane_hue_logger')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG)
    logger.addHandler(stream_handler)


class MockBridge:
    def __init__(self, ip):
        self.lights = []
        pass

    def connect(self):
        logger.debug("bridge.connect")


if __name__ == '__main__':
    main()
