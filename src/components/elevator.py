import logging
from wpilib import DigitalInput, Encoder, Talon, SmartDashboard
from common import constants
from common.syncgroup import SyncGroup
from robotpy_ext.common_drivers import units
from common.util import limit, AutoNumberEnum
from . import Component

log = logging.getLogger("elevator")

MAX_POS = 26750
MIN_POS = units.convert(units.inch, units.tick, 1 / 8)
PID_TOLERANCE = units.convert(units.inch, units.tick, 1 / 8)


class Elevator(Component):

	def __init__(self):
		super().__init__()
		self._motor = SyncGroup(Talon, constants.motors.elevator_motor)
		self._encoder = Encoder(constants.sensors.elevator_encoder_a, constants.sensors.elevator_encoder_b, True)
		self._halleffect = DigitalInput(constants.sensors.elevator_hall_effect)
		self._photosensor = DigitalInput(constants.sensors.photosensor)

		# for I & D
		self._prev_error = 0
		self._integral = 0

		# for moving
		self.desired_position = 0
		self.stack_offset = 0

		self.zeroed = False
		self.ready_to_zero = False
		self.intaking = False

	def stop(self):
		self._motor.set(0)

	def update(self):
		if not True:#self.zeroed:
			# goes up until the elevator is raised off the hall effect.
			if self.ready_to_zero:
				self._motor.set(.1)
				if self._halleffect.get():
					self.reset_encoder()
					self.zeroed = True

			elif not self._halleffect.get():  # wait till we get into the hall effect first
				self.ready_to_zero = True
				self._motor.set(-.1)

		else:
			if self.intaking:
				if self.at_setpoint():
					if self.has_tote():
						self.set(constants.tunable.elevator_offset + units.convert(units.tote, units.tick, self.stack_offset))  # go under tote and grab
					else:
						self.set(constants.tunable.elevator_offset + units.convert(units.tote, units.tick, self.stack_offset + 1))  # go back up with tote
			else:
				self.set(constants.tunable.neutral_position)

			self.do_pid()

	def set(self, pos):  # translates levels 0-6 into encoder value
		if not self.desired_position == round(pos):
			self.desired_position = min(max(MIN_POS, self.desired_position), MAX_POS)
			self._integral = 0

	def reset_encoder(self):
		self._encoder.reset()
		self._prev_error = 0
		self._integral = 0

	def do_pid(self):
		error = self.desired_position - self.position()

		derivative = (error - self._prev_error) / constants.general.control_loop_wait_time

		self._integral += error * constants.general.control_loop_wait_time
		self._integral = limit(self._integral, constants.tunable.kI_limit)

		p = constants.tunable.kP * error
		i = constants.tunable.kI * self._integral
		d = constants.tunable.kD * derivative

		if error > 0:  # goin up
			power_limit = constants.tunable.up_power_limit
		else:  # runs even if error is 0, but that doesn't matter.
			power_limit = constants.tunable.down_power_limit

		self._motor.set(limit(p + i + d, power_limit))

		self._prev_error = error

	def has_tote(self):
		return self._photosensor.get()

	def position(self):
		return self._encoder.getDistance()

	def at_setpoint(self):
		return abs(self.desired_position - self.position()) < PID_TOLERANCE

	def update_smartdashboard(self):
		SmartDashboard.putNumber("Elevator Setpoint", self.desired_position)
		SmartDashboard.putString("Elevator Position", self.position())
		SmartDashboard.putBoolean("Elevator at Setpoint", self.at_setpoint())

		SmartDashboard.putNumber("Elevator Integral", self._integral)

		SmartDashboard.putBoolean("ready_to_zero", self.ready_to_zero)

	# TODO change robot.py sets to offset changes

	# TODO in constants.py

	# Change so every component can populate a list of tunable variables that automatically get put into smartdashboard
	# 	self.elevator_offset = 0
	# 	self.neutral_position = 0
	# TODO pip install manhole
	# >>> import manhole
	# >>> manhole.install()