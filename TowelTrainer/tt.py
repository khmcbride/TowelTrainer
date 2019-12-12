import micropython
import sys
import machine
import utime as time
import uerrno
from machine import TouchPad, Pin
import ujson as json
import uio as io
import socket
import gc
import os


class Contraption:
	
	DIR_TOWARD_TOP = 1
	DIR_TOWARD_BOTTOM = 0
	
	LED_R = 21
	LED_G = 19
	LED_B = 18

	INIT = 36
	RUN = 39

	MS_TOP = 34
	MS_BOTTOM = 35

	SM_AXIAL = 33
	SM_SLED = 25
	SM_SLED_DIR = 26
	SM_SLED_ENA = 22

	DEBUG_MODE = False

	@staticmethod
	def print(string):
		if Contraption.DEBUG_MODE:
			print(string)

	def int_callback(self, pin):
		for p in self.get_interrupt_events(): 
			if (p.pin is pin or p.pin == pin):
				p.activate()

	def poll_callback(self, pin):
		None

	def main_loop(self): 
		while True:
			self.handle_events()
			time.sleep_ms(100)
			#gc.collect()
			
			
	def handle_events(self):
		#if any new non-interrupt pins indicate selection, activate them
		#check all events and manage bounce
		for p in self.pin_events:
			#print('interrupt:{} is_activated:{} pin.value:{}'.format(p.interrupt, p.is_activated, p.pin.value()))
			if p.interrupt == False and p.is_activated == False and p.pin.value() == 0:
				Contraption.print('Non-interrupt event: {}'.format(p.desc))
				p.activate()
			if p.is_activated and p.pin.value() == 0:
				Contraption.print('Handling {} event: {}ms'.format(p.desc, time.ticks_ms() - p.last_activation))
				p.check_for_long_press()
			elif p.is_activated and p.pin.value() == 1 and time.ticks_ms() - p.last_bounce > Event.debounce_ms:
				p.attempt_reset()


	def reset_machine(self):
		if self.is_running:
			print('!!!ENDING RUN!!!')
			self.sm_towel.halt_rotation()
			self.sm_sled.halt_rotation()
			self.is_running = False
			self.passes_remaining = self.SLED_PASSES
			print('!!!run aborted!!!')
			return
		else:
			print('!!!resetting machine!!!')
		
		self.is_resetting = True
		self.set_led(red=1020,blue=1020)
		# bring tape roller sled to rear position until rear endstop is hit
		self.set_sled_dir_toward_top()
		self.sm_sled.begin_rotation()
		
		

	def run_machine(self):
		if self.is_endstop_top_activated() == False:
			print('Cannot start machine until it has been reset.')
			self.set_led(red=1020, green=1020)
			return
		if self.is_running:
			print('!!!already running!!!')
			return
		
		print('!!!starting machine!!!')
		self.set_led(blue=1020)
		self.is_running = True
		self.passes_remaining = self.SLED_PASSES
		self.set_sled_dir_toward_bottom()
		# enable and start spinning towel motors clockwise 
		
		self.sm_towel.begin_rotation()
		time.sleep_ms(self.ROTATION_HEADSTART)
		self.sm_sled.begin_rotation()
		
		
	def hit_top(self):
		#print('Hit top {}'.format(self.p_hit_top.value()))
		self.sm_sled.halt_rotation()
		
		if self.is_running and self.get_sled_dir() == Contraption.DIR_TOWARD_TOP:
			self.set_sled_dir_toward_bottom()
			time.sleep_ms(self.ROTATION_HEADSTART)
			self.sm_sled.begin_rotation()
			self.passes_remaining -= 1
			print('Hit top, {} passes remain.'.format(self.passes_remaining))
			if self.passes_remaining == 0:
				self.stop_all_motors()
				print('Finished...')
				self.set_led(red=1020)
		elif self.is_resetting:
			self.set_sled_dir_toward_bottom()
			self.stop_all_motors()
			self.set_led(green=1020)
			self.is_resetting = False		

	def hit_bottom(self):
		#print('Hit bottom {}'.format(self.p_hit_bottom.value()))
		self.sm_sled.halt_rotation()

		if self.is_running and self.get_sled_dir() == Contraption.DIR_TOWARD_BOTTOM:
			self.set_sled_dir_toward_top()
			time.sleep_ms(self.ROTATION_HEADSTART)
			self.sm_sled.begin_rotation()
			self.passes_remaining -= 1
			print('Hit bottom, {} passes remain.'.format(self.passes_remaining))
			if self.passes_remaining == 0:
				self.stop_all_motors()
				print('Finished...')
				self.set_led(green=1020)
		

	def stop_all_motors(self):
		self.sm_towel.halt_rotation()
		self.sm_sled.halt_rotation()
		self.is_running = False
		self.is_resetting = False

	def set_sled_dir_toward_top(self):
		self.sm_sled.set_dir(Contraption.DIR_TOWARD_TOP)

	def set_sled_dir_toward_bottom(self):
		self.sm_sled.set_dir(Contraption.DIR_TOWARD_BOTTOM)
		
	def get_sled_dir(self):
		return self.sm_sled.current_dir

	def is_endstop_top_activated(self):
		return next(filter( lambda x: x.desc == "Hit_Top", self.pin_events )).is_activated

	def is_endstop_bottom_activated(self):
		return next(filter( lambda x: x.desc == "Hit_Bottom", self.pin_events )).is_activated

	def get_non_interrupt_events(self):
		return filter( lambda x: x.interrupt == False, self.pin_events )

	def get_interrupt_events(self):
		return filter( lambda x: x.interrupt == True, self.pin_events )

	def set_led(self, red = None, green = None, blue = None):
		use_led = True

		if not use_led:
			self.red.deinit()
			self.green.deinit()
			self.blue.deinit()
			return

		if red:
			self.red = machine.PWM(self.p_led_r, 60, duty=red)
		else:
			self.red.deinit()
		
		if green:
			self.green = machine.PWM(self.p_led_g, 60, duty=green)
		else:
			self.green.deinit()
		
		if blue:
			self.blue = machine.PWM(self.p_led_b, 60, duty=blue)
		else:
			self.blue.deinit()

	def start_webserver(self):

		self.stop_all_motors()
		self.set_led(blue=1020, green=1020)
		print("Starting Web Configuration Mode")
	
		addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
		s = socket.socket()
		s.bind(addr)
		s.listen(1)

		print('listening on', addr)

		while True:
			cl, addr = s.accept()
			print('client connected from', addr)
			c_head = cl.recv(2048).decode('UTF-8')
			first_line = c_head.splitlines()[0]
			verb = None

			if "POST" in first_line:
				verb = 'post'
				form_data = c_head.split('form-data; ')[2:]
				for p in form_data:
					element = p.splitlines()
					#['name="rotation_rate"', '', '150', '------WebKitFormBoundaryiA60g5J0Q8UQmDS7', 'Content-Disposition: ']
					key = element[0]
					value = int(element[2])
					if 'rotation_rate' in key:
						self.ROTATION_RATE = value
					elif 'rotation_headstart_ms' in key:
						self.ROTATION_HEADSTART = value
					elif 'sled_rate' in key:
						self.SLED_RATE = value
					elif 'sled_passes' in key:
						self.SLED_PASSES = value
					elif 'sled_endstop_pause_ms' in key:
						self.SLED_ENDSTOP_PAUSE = value
				
				self.save_config()
				self.apply_config()

			elif "GET" in first_line:
				verb = 'get'

			#get html template
			html = None
			with open('index.html') as reader:
				html = reader.read()
			html = html\
			.replace('[rotation_rate]',str(self.ROTATION_RATE))\
			.replace('[rotation_headstart_ms]',str(self.ROTATION_HEADSTART))\
			.replace('[sled_rate]',str(self.SLED_RATE))\
			.replace('[sled_passes]',str(self.SLED_PASSES))\
			.replace('[sled_endstop_pause_ms]',str(self.SLED_ENDSTOP_PAUSE))

			header = 'HTTP/1.1 200 OK\n'
			header += 'Content-Type: text/html\n'
			header += 'Connection: close\n\n'
			response = header.encode()
			response += html.encode()

			cl.send(response)
			cl.close()

			if (verb == 'post'):
				s.close()
				gc.collect()

				self.set_led(red=1020)
				time.sleep_ms(400)
				self.set_led(blue=1020)
				time.sleep_ms(400)
				self.set_led(green=1020)
				time.sleep_ms(400)

				if not self.is_endstop_bottom_activated():
					self.reset_machine()
				return

	def apply_config(self):
		#JSON config sample
		#{
		#  "rotation_rate": 150,
		#  "rotation_headstart_ms": 2000, 
		#  "sled_rate": 100,
		#  "sled_passes": 3,
		#  "sled_endstop_pause_ms":  1000
		#}
		data = None
		with open('config.json', 'r') as json_file:
			data = json.load(json_file)
			for p in data:
				print('{}: {}'.format(p, data[p]))
		
		self.ROTATION_RATE = data["rotation_rate"]
		self.ROTATION_HEADSTART = data["rotation_headstart_ms"]
		self.SLED_RATE = data["sled_rate"]
		self.SLED_PASSES = data["sled_passes"]
		self.SLED_ENDSTOP_PAUSE = data["sled_endstop_pause_ms"]

		self.sm_sled.set_step_time_in_Hz(self.SLED_RATE)
		self.sm_towel.set_step_time_in_Hz(self.ROTATION_RATE)

	def save_config(self):
		#JSON config sample
		#{
		#  "rotation_rate": 150,
		#  "rotation_headstart_ms": 2000, 
		#  "sled_rate": 100,
		#  "sled_passes": 3,
		#  "sled_endstop_pause_ms":  1000
		#}
		data = None
		with open('config.json', 'r') as json_file:
			data = json.load(json_file)
		
			data["rotation_rate"] = self.ROTATION_RATE
			data["rotation_headstart_ms"] = self.ROTATION_HEADSTART
			data["sled_rate"] = self.SLED_RATE
			data["sled_passes"] = self.SLED_PASSES
			data["sled_endstop_pause_ms"] = self.SLED_ENDSTOP_PAUSE


		os.remove('config.json')
		with open('config.json', 'w') as f:
			json.dump(data, f)

	def __init__(self):
		gc.enable()

		self.is_running = False
		self.is_resetting = False
		self.passes_remaining = 0
		self.last_ms_triggered = None

		#set up color status indicator
		self.p_led_r = machine.Pin(Contraption.LED_R, machine.Pin.OUT, value=0)
		self.p_led_g = machine.Pin(Contraption.LED_G, machine.Pin.OUT, value=0)
		self.p_led_b = machine.Pin(Contraption.LED_B, machine.Pin.OUT, value=0)
		self.red = machine.PWM(self.p_led_r, 60, duty=512)
		self.green = machine.PWM(self.p_led_g, 60, duty=512)
		self.blue = machine.PWM(self.p_led_b, 60, duty=512)
		
		self.set_led(red=1020)
		time.sleep_ms(400)

		#set up motors
		self.p_sm1 = machine.Pin(Contraption.SM_AXIAL, machine.Pin.OUT)
		self.sm_towel = Stepper(self.p_sm1)

		self.p_sm2 = machine.Pin(Contraption.SM_SLED, machine.Pin.OUT)
		self.p_sm2_dir = machine.Pin(Contraption.SM_SLED_DIR, machine.Pin.OUT)
		self.p_sm2_ena = machine.Pin(Contraption.SM_SLED_ENA, machine.Pin.OUT)
		self.sm_sled = Stepper(self.p_sm2, dir_pin=self.p_sm2_dir, sleep_pin=self.p_sm2_ena)
		self.sm_sled.steps_per_rev = 200

		#pull JSON configuration and apply it
		self.apply_config()

		self.set_led(blue=1020)
		time.sleep_ms(400)

		#set up input pins for endstops and controller buttons
		self.p_init = machine.Pin(Contraption.INIT, machine.Pin.IN)
		self.p_run = machine.Pin(Contraption.RUN, machine.Pin.IN)
		self.p_hit_top = machine.Pin(Contraption.MS_TOP, machine.Pin.IN)
		self.p_hit_bottom = machine.Pin(Contraption.MS_BOTTOM, machine.Pin.IN)
		
		self.p_hit_top.irq(trigger=machine.Pin.IRQ_FALLING, handler=self.int_callback)
		self.p_hit_bottom.irq(trigger=machine.Pin.IRQ_FALLING, handler=self.int_callback)

		#set up event handlers
		self.pin_events = [
			Event(Contraption.INIT, "Init", self.p_init, callback=self.reset_machine, long_press_callback=self.start_webserver, interrupt=False),
			Event(Contraption.RUN, "Run",  self.p_run, callback=self.run_machine, interrupt=False),
			Event(Contraption.MS_TOP, "Hit_Top", self.p_hit_top, callback=self.hit_top),
			Event(Contraption.MS_BOTTOM, "Hit_Bottom",  self.p_hit_bottom, callback=self.hit_bottom)
		]

		self.set_led(green=1020)
		time.sleep_ms(400)

		if not self.is_endstop_bottom_activated():
			self.reset_machine()

		print('\n...waiting for input')
		
		self.main_loop()
		print('done...')

	
class Event(object):
	
	debounce_ms = 60
	long_press_ms = 3000

	def __init__(self, id, desc, pin, is_activated=False, callback=None, long_press_callback=None, interrupt=True):
		self.id = id
		self.desc = desc
		self.pin = pin
		self.last_activation = time.ticks_ms()
		self.last_bounce = time.ticks_ms()
		self.is_activated = False
		self.callback = callback
		self.long_press_callback = long_press_callback
		self.interrupt = interrupt 
		self.is_long_pressed = False

	def activate(self):
		self.last_bounce = time.ticks_ms()
		Contraption.print('{} activate attempt- state={} activated={} last bounce={}'.format(self.desc, self.pin.value(), self.is_activated, time.ticks_ms() - self.last_bounce))
		if not self.is_activated and time.ticks_ms() - self.last_bounce < Event.debounce_ms:
			self.is_activated = True
			self.last_activation = time.ticks_ms()
			time.sleep_ms(Event.debounce_ms)
			self.callback()
		else:
			#Contraption.print('unexpected bounce {}ms'.format( time.ticks_ms() - self.last_bounce))
			None

	def attempt_reset(self):
		#Contraption.print('reset attempt- state={} activated={} last bounce={}'.format(self.pin.value(), self.is_activated, time.ticks_ms() - self.last_bounce))
		if self.is_activated and self.pin.value() == 1 and time.ticks_ms() - self.last_bounce > Event.debounce_ms:
			Contraption.print('{} deactivated {}ms'.format(self.desc, time.ticks_ms() - self.last_bounce))
			self.is_activated = False
			self.is_long_pressed = False

	def check_for_long_press(self):
		if self.is_activated and self.pin.value() == 0 and not self.is_long_pressed and time.ticks_ms() - self.last_bounce > Event.long_press_ms:
			self.is_long_pressed = True
			if self.long_press_callback:
				self.long_press_callback()

class Stepper:

	def __init__(self, step_pin, dir_pin = None, sleep_pin = None, rate = 200):
		"""Initialise stepper."""
		self.stp = step_pin
		self.dir = dir_pin
		self.slp = sleep_pin
		
		self.current_dir = None

		self.stp.init(Pin.OUT)
		if dir_pin: self.dir.init(Pin.OUT)
		if sleep_pin: self.slp.init(Pin.OUT)

		self.steps_per_rev = 400

		self.set_step_time_in_Hz(rate)

		self.pwm_stepper = None

		if self.slp: self.power_off()

	def power_on(self):
		"""Power on stepper."""
		self.slp.value(0)

	def power_off(self):
		"""Power off stepper."""
		self.slp.value(1)

	def set_dir(self, dir):
		self.current_dir = dir
		self.dir.value(self.current_dir)

	def set_step_time_in_Hz(self, rate):
		Contraption.print("-[] step rate set to {}Hz (1 step every {}ms)".format(rate, 1000/rate))
		self.rate = rate

	def begin_rotation(self):
		if self.slp:
			self.power_on()
		self.pwm_stepper = machine.PWM(self.stp, self.rate, duty=400)
		Contraption.print('-[] running motor {}'.format(self))

	def halt_rotation(self):
		if self.slp:
			self.power_off()
		if self.pwm_stepper:
			self.pwm_stepper.deinit()
			Contraption.print('-[] stopping motor {}'.format(self))

def main():
	#c = Contraption()
	None

if __name__ == '__main__':
	main()
