# progress.py
#
# Copyright (C) 2015-2018 Kano Computing Ltd.
# License: http://www.gnu.org/licenses/gpl-2.0.txt GNU GPL v2
#
# Managing the upgrade procedure.


import os
import sys

from kano.logging import logger
import monitor_heartbeat
from kano_updater.reporting import send_crash_report


def encode(x):
    """Placeholder function to translate encoding only when necessary"""
    return x.encode('utf-8') if isinstance(x, unicode) else x


class ProgressError(Exception):
    pass


class Relaunch(Exception):
    pid = None


class Phase(object):
    '''
    A single task

    :param name: The identifier for the phase
    :param label: The human readable label for the phase
    :param weight: Metric for task size. Often used as percentage of the whole
    :param is_main: Should subtasks be labelled as belonging to this task
    :type name: str
    :type label: str
    :type weight: int or float
    :type is_main: bool
    '''

    def __init__(self, name, label, weight=1, is_main=False):
        self.name = name
        self.label = label
        self.weight = weight

        self.start = 0
        self.length = 100
        self.parents = []

        self.step_count = 1
        self._step = 0

        self.is_main = is_main

    @property
    def percent(self):
        factor = float(self.step) / self.step_count
        return int(factor * 100)

    @property
    def global_percent(self):
        factor = float(self.step) / self.step_count
        return int(self.start + factor * self.length)

    @property
    def step(self):
        return self._step

    @step.setter
    def step(self, step):
        if step < self.step_count:
            self._step = step
        else:
            self._step = self.step_count

    def get_main_phase(self):
        if self.is_main:
            return self

        for phase in self.parents:
            if phase.is_main:
                return phase

        return self


class Progress(object):
    """
        The base class for progress reporting of both downloads and
        installations. Subclass it and pass an instance to either
        the download() or install() functions to be notified of
        what's going on.
    """

    def __init__(self):
        root_phase = Phase('root', _("The root phase"), 1)

        self._phases = [root_phase]
        self._current_phase_idx = 0

    def start(self, phase_name):
        """
            Starts a certain phase of the progress.

            This doesn't need to be called for steps.

            :param phase_name: A string that identifies the current phase.
            :type phase_name: str
        """
        phase = self._get_phase_by_name(phase_name)

        self._current_phase_idx = self._phases.index(phase)

        log = "global({}%) local({}%): " \
              "Starting '{}' ({}) [main phase '{}' ({})]".format(
                  phase.global_percent,
                  phase.percent,
                  phase.label.encode('utf-8'),
                  phase.name,
                  phase.get_main_phase().label.encode('utf-8'),
                  phase.get_main_phase().name
              )
        logger.info(log)

        # Calculate current progress and emit an event
        monitor_heartbeat.heartbeat()
        self._change(phase, phase.label)

    def get_current_phase(self):
        return self._phases[self._current_phase_idx]

    def split(self, *subphases, **kwargs):
        if 'phase_name' not in kwargs:
            phase = self.get_current_phase()
        else:
            phase = self._get_phase_by_name(kwargs['phase_name'])

        start = phase.start
        weight_sum = sum([p.weight for p in subphases])
        for subphase in subphases:
            # FIXME: Prevent splitting into identical phases
            if subphase.name != phase.name \
               and self._get_phase_by_name(subphase.name, False):

                msg = "Phase '{}' already exists".format(phase.name)
                raise ValueError(msg)

            weight_factor = float(subphase.weight) / weight_sum

            subphase.length = weight_factor * phase.length

            subphase.start = start
            start += subphase.length

            subphase.parents = [phase] + phase.parents

        # Implant the subphases into the phase list in place of the parent
        idx = self._phases.index(phase)
        self._phases = self._phases[0:idx] + list(subphases) + \
            self._phases[idx + 1:]

    def init_steps(self, phase_name, step_count):
        phase = self._get_phase_by_name(phase_name)
        phase.step_count = step_count
        phase.step = 0

    def set_step(self, phase_name, step, msg):
        phase = self._get_phase_by_name(phase_name)
        phase.step = step

        log = "global({}%) local({}%): " \
              "Next step in '{}' ({})  [main phase '{}' ({})]: {}".format(
                  phase.global_percent,
                  phase.percent,
                  phase.label.encode('utf-8'),
                  phase.name,
                  phase.get_main_phase().label.encode('utf-8'),
                  phase.get_main_phase().name,
                  encode(msg)
              )
        logger.info(log)
        monitor_heartbeat.heartbeat()
        self._change(phase, msg)

    def next_step(self, phase_name, msg):
        phase = self._get_phase_by_name(phase_name)
        self.set_step(phase_name, phase.step + 1, msg)

    def _get_phase_by_name(self, name, do_raise=True):
        for phase in self._phases:
            if phase.name == name:
                return phase

        if do_raise:
            raise ValueError("Phase '{}' doesn't exist".format(name))

    def fail(self, msg):
        phase = self._phases[self._current_phase_idx]
        logger.error("Error {}: {}".format(phase.label.encode('utf-8'), encode(msg)))
        send_crash_report(
            'Updater failure',
            'Failed with error: {}'.format(msg)
        )
        self._error(phase, msg)

    def prompt(self, msg, question, answers=None):
        if not answers:
            answers = [_("yes"), _("no")]

        if len(answers) <= 0:
            raise ValueError("The must be at least one answer to the question!")

        return self._prompt(msg, question, answers)

    def finish(self, msg):
        logger.info("Complete: {}".format(msg))
        self._done(msg)

    def relaunch(self):
        logger.info("Scheduling relaunch")
        monitor_heartbeat.heartbeat()
        self._relaunch()

    def abort(self, msg):
        """
            Akin a an exception
        """
        phase = self._phases[self._current_phase_idx]
        logger.error("Aborting {}, {}".format(phase.label, msg))
        send_crash_report(
            'Updater aborted',
            'Aborted with error: {}'.format(msg)
        )
        self._abort(phase, msg)

    def _change(self, phase, msg):
        """
            The callback that is triggered for each progress change.

            IMPORTANT: This needs to be implemented by child.

            :param phase: The currently active phase
            :type percent: Phase

            :param msg: Message for the UI.
            :type msg: str
        """

        raise NotImplementedError("The _change callback must be implemented")

    def _error(self, phase, msg):
        raise NotImplementedError("The _error callback must be implemented")

    def _abort(self, phase, msg):
        raise NotImplementedError("The _abort callback must be implemented")

    def _done(self, msg):
        raise NotImplementedError("The _done callback must be implemented")

    def _prompt(self, msg, question, answers):
        """
            Prompt the user for input.

            :param msg: A message to pass on to user.
            :type msg: str

            :param question: The question asked.
            :type question: str

            :param answers: The possible options.
            :type answers: list of str

            :return: One of the options.
            :rtype: str
        """

        raise NotImplementedError("The _prompt callback must be implemented")

    def _relaunch(self):
        """
            This one is implemented here, because we need to relaunch
            even if we don't care about the progress.
        """
        raise Relaunch()


class DummyProgress(Progress):
    def start(self, phase_name):
        pass

    def split(self, phase_name, *subphases):
        pass

    def init_steps(self, phase_name, step_count):
        pass

    def set_step(self, phase_name, step, msg):
        pass

    def next_step(self, phase_name, msg):
        pass

    def fail(self, msg):
        pass

    def abort(self, msg):
        pass

    def finish(self, msg):
        pass

    def prompt(self, msg, question, answers=None):
        pass

    # TODO: Not disabling this method, we need to relaunch in any case
    # def relaunch(self):
    #     pass


class CLIProgress(Progress):
    def _change(self, phase, msg):
        print encode("{}%: {}".format(phase.global_percent, encode(msg)))

    def _error(self, phase, msg):
        print _("ERROR: {}").format(encode(msg))

    def _abort(self, phase, msg):
        print _("Aborting {}, {}").format(phase.label, encode(msg))

    def _done(self, msg):
        print encode(msg)

    def _relaunch(self):
        raise Relaunch()

    def _prompt(self, msg, question, answers):
        if not os.isatty(sys.stdin.fileno()):
            warn = (
                "No tty, selecting the default answer for '{}' which is: {}"
                .format(question.encode('utf-8'), answers[0].encode('utf-8'))
            )
            logger.warn(warn)
            return answers[0]
        else:
            print encode(msg)
            norm_answers = [answer.strip().lower() for answer in answers]
            q_str = u"{} [{}]: ".format(question, "/".join(norm_answers))

            answer = raw_input(q_str)
            while answer.strip().lower() not in norm_answers:
                print _("Type one of these:  {}").format(u" ".join(norm_answers)).encode('utf-8')
                answer = raw_input(q_str)

        return answer
