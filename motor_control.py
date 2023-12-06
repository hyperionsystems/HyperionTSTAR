import RPi.GPIO as GPIO
import time


class MotorControl:

    def __init__(self):

        # define pins
        self.jib_pul = 20
        self.jib_dir = 16
        self.jib_pins = [self.jib_pul, self.jib_dir]
        self.rail_pul = 12
        self.rail_dir = 25
        self.rail_pins = [self.rail_pul, self.rail_dir]
        self.winch_pul = 24
        self.winch_dir = 23
        self.winch_pins = [self.winch_pul, self.winch_dir]

        self.duty_cycle = 50
        self.pwm_on = (self.duty_cycle / 50)
        self.pwm_off = ((100 - self.duty_cycle) / 50)

        # define delays

        # large delay between jib steps (1 RPM)
        self.jib_pulse = 0.000006
        self.jib_delay = [self.jib_pulse * self.pwm_on, self.jib_pulse * self.pwm_off]

        # large delay between rail steps
        self.rail_pulse_slow = 0.001
        self.rail_delay_slow = [self.rail_pulse_slow * self.pwm_on, self.rail_pulse_slow * self.pwm_off]

        # small delay between rail steps
        self.rail_pulse_fast = 0.0009
        self.rail_delay_fast = [self.rail_pulse_fast * self.pwm_on, self.rail_pulse_fast * self.pwm_off]

        # large delay between winch steps
        self.winch_pulse_slow = 0.001
        self.winch_delay_slow = [self.winch_pulse_slow * self.pwm_on, self.winch_pulse_slow * self.pwm_off]

        # small delay between winch steps (300 RPM)
        self.winch_pulse_fast = 0.0009
        self.winch_delay_fast = [self.winch_pulse_fast * self.pwm_on, self.winch_pulse_fast * self.pwm_off]

        self.init_pins()

    # initialize GPIO pins
    def init_pins(self):

        # Define pins
        pins = self.jib_pins + self.rail_pins + self.winch_pins

        # Set GPIO numbering mode
        GPIO.setmode(GPIO.BCM)
        # Set pins as output
        for pin in pins:
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)

    def rotate_motor(self, pins, steps, direction, delay):

        pul_pin, dir_pin = pins
        GPIO.output(dir_pin, direction)
        for _ in range(steps):
            GPIO.output(pul_pin, GPIO.HIGH)
            time.sleep(delay[0])
            GPIO.output(pul_pin, GPIO.LOW)
            time.sleep(delay[1])

    def deploy_part1(self, direction, jib_steps):

        # Rotate jib to ASEP
        self.rotate_motor(self.jib_pins, steps=jib_steps, direction=direction, delay=self.jib_delay)

    def deploy_part2(self, steps):

        # Orient crane to ASEP
        self.rotate_motor(self.winch_pins, steps=steps[0], direction=1, delay=self.winch_delay_fast)
        self.rotate_motor(self.rail_pins, steps=steps[1], direction=1, delay=self.rail_delay_fast)

    def deploy_part3(self, direction, steps):

        # Deploy ASEP to retrieval envelope
        print("Deploying ASEP to retrieval envelope")
        self.rotate_motor(self.winch_pins, steps=steps[0], direction=0, delay=self.winch_delay_slow)
        self.rotate_motor(self.jib_pins, steps=steps[1], direction=not direction, delay=self.jib_delay)
        self.rotate_motor(self.rail_pins, steps=steps[2], direction=1, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[3], direction=1, delay=self.winch_delay_slow)
        self.rotate_motor(self.rail_pins, steps=steps[4], direction=0, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[5], direction=0, delay=self.winch_delay_slow)
        self.rotate_motor(self.rail_pins, steps=steps[6], direction=0, delay=self.rail_delay_fast)

    def orient_for_retrieve(self, direction, steps):
        # Orient crane to ASEP
        print("Orienting for Retrieval")
        self.rotate_motor(self.jib_pins, steps=steps[0], direction=direction, delay=self.jib_delay)
        self.rotate_motor(self.rail_pins, steps=steps[1], direction=1, delay=self.rail_delay_fast)
        self.rotate_motor(self.winch_pins, steps=steps[2], direction=1, delay=self.winch_delay_fast)
        self.rotate_motor(self.rail_pins, steps=steps[3], direction=1, delay=self.rail_delay_slow)

    def return_from_orient(self, steps, direction):
        # Return crane from orienting for retrieval
        print("Returning from orienting for retrieval")
        self.rotate_motor(self.rail_pins, steps=steps[3], direction=0, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[2], direction=0, delay=self.winch_delay_fast)
        self.rotate_motor(self.rail_pins, steps=steps[1], direction=0, delay=self.rail_delay_fast)
        self.rotate_motor(self.jib_pins, steps=steps[0], direction=not direction, delay=self.jib_delay)

    def reorient_for_retrieve(self, steps, directions):
        # Orient crane to ASEP
        print("Orienting for Retrieval")
        self.rotate_motor(self.rail_pins, steps=steps[0], direction=0, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[1], direction=0, delay=self.winch_delay_slow)
        self.rotate_motor(self.jib_pins, steps=steps[2], direction=directions[0], delay=self.jib_delay)
        self.rotate_motor(self.rail_pins, steps=steps[3], direction=directions[1], delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[4], direction=1, delay=self.winch_delay_slow)
        self.rotate_motor(self.rail_pins, steps=steps[5], direction=1, delay=self.rail_delay_slow)

    def reorient_for_deploy(self, direction, steps):
        self.rotate_motor(self.rail_pins, steps=steps, direction=direction, delay=self.rail_delay_slow)

    def retrieve_asep(self, steps, ret_pos, direction):
        # Retrieve ASEP to baseplate
        print("Retrieving to baseplate")
        self.rotate_motor(self.winch_pins, steps=steps[0], direction=0, delay=self.winch_delay_slow)
        self.rotate_motor(self.jib_pins, steps=steps[1], direction=not direction, delay=self.jib_delay)
        self.rotate_motor(self.rail_pins, steps=steps[2], direction=1, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[3], direction=0, delay=self.winch_delay_slow)
        self.rotate_motor(self.rail_pins, steps=steps[4], direction=0, delay=self.rail_delay_slow)
        self.rotate_motor(self.jib_pins, steps=steps[5], direction=ret_pos, delay=self.jib_delay)
        self.rotate_motor(self.winch_pins, steps=steps[6], direction=1, delay=self.winch_delay_slow)
        self.rotate_motor(self.rail_pins, steps=steps[7], direction=0, delay=self.rail_delay_slow)
        self.rotate_motor(self.winch_pins, steps=steps[8], direction=0, delay=self.winch_delay_fast)

    def clean_up(self):
        GPIO.cleanup()
