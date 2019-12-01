import sys
import _machine
import time
import uerrno
from _machine import TouchPad, Pin



 
p25 = machine.Pin(25, machine.Pin.IN, machine.Pin.PULL_UP)
p26 = machine.Pin(26, machine.Pin.IN, machine.Pin.PULL_UP)

def callbackInit(pin):
	print('callback on pin 25')
	print(pin)
	global interruptCounter
	interruptCounter = interruptCounter+1

def callbackBegin(pin):
	print('callback on Begin Button')
	global interruptCounter
	interruptCounter = interruptCounter+1

p25.irq(trigger=machine.Pin.IRQ_FALLING, handler=callbackInit)
p26.irq(trigger=machine.Pin.IRQ_FALLING, handler=callbackBegin)



def touch():
	t = TouchPad(Pin(14))
	#print('hello')
	while True:
		print(t.read())
		time.sleep_ms(200)

def watch_ints(): 
	while True:
		global interruptCounter
		try:
			if interruptCounter > 0:
				print("Interrupt detected!")
				state = machine.disable_irq()
				print("dis")
				interruptCounter = interruptCounter-1
				print("inc")
				machine.enable_irq(state)
				print("enbl")
			
				totalInterruptsCounter = totalInterruptsCounter+1
			#	print("Interrupt has occurred: " + str(totalInterruptsCounter))
			time.sleep_ms(500)
		except OSError as ex:
			print(uerrno.errorcode[ex.args[0]])
			print('Unexpected error: {}'.format(ex.args[0]))
		print('.{}'.format(interruptCounter))

def main():
	global interruptCounter
	interruptCounter = 0
	global totalInterruptsCounter
	totalInterruptsCounter = 0

	print('main()')
	watch_ints()
	print('done...')

if __name__ == '__main__':
	main()
