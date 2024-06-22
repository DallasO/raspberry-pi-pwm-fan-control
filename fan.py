#!/usr/bin/python

# python modules
# import lgpio as sbc
import RPi.GPIO as gpio
# import pigpio
import time
import sys
import os
import sys, getopt
import atexit

from w1thermsensor import W1ThermSensor

# Helper functions

# Handle getting current time
def now():
    return time.perf_counter()

# Configuration
PWM_GPIO_NR = 18        # PWM gpio number used to drive PWM fan (gpio18 = pin 12)
RPM_GPIO_NR = 23
TEMP_GPIO_NR = 4
WAIT_TIME = 1           # [s] Time to wait between each refresh
PWM_FREQ = 10000        # [Hz] 10kHz PWM frequency
TEMP_SOURCE = 'cpu'

# Configurable temperature and fan speed
MIN_TEMP = 40 # 104F
MIN_TEMP_OFFSET = 4
MAX_TEMP = 60 # 140F
FAN_LOW = 20
FAN_HIGH = 100
FAN_OFF = 0
FAN_MAX = 100
MIN_RUN_TIME = 5 * 60 # 5 minutes
MIN_SLEEP_TIME = 60  # 1 minute

# Time trackers
ON_TIME = now() - MIN_RUN_TIME
OFF_TIME = now() - MIN_SLEEP_TIME

# logging and metrics (enable = 1)
VERBOSE = 0
NODE_EXPORTER = 0

# State variables
currentSpeed = FAN_OFF

# State functions
def fanIsOff():
    return currentSpeed == FAN_OFF

HELP_TEXT = 'fan.py [--min-temp=40] [--max-temp=70] [--fan-low=20] [--fan-high=100] [--wait-time=1] [--pwm-gpio=18] [--pwm-freq=10000] [--node-exporter] [-v|--verbose] [-h|--help]'

# parse input arguments
try:
   opts, args = getopt.getopt(sys.argv[1:],"hv",["min-temp=","max-temp=","fan-low=","fan-high=","wait-time=","help","pwm-gpio=","pwm-freq=", "rpm-gpio=", "temp-gpio=", "min-temp-offset=", "min-run-time=", "min-sleep-time=","verbose","node-exporter", "cpu", "sensor"])
except getopt.GetoptError:
   print(HELP_TEXT)
   sys.exit(2)
for opt, arg in opts:
   if opt in ("-h", "--help"):
      print(HELP_TEXT)
      sys.exit()
   elif opt in ("-v", "--verbose"):
      VERBOSE = 1
   elif opt in ("--min-temp"):
      MIN_TEMP = int(arg)
   elif opt in ("--max-temp"):
      MAX_TEMP = int(arg)
   elif opt in ("--fan-low"):
      FAN_LOW = int(arg)
   elif opt in ("--fan-high"):
      FAN_HIGH = int(arg)
   elif opt in ("--wait-time"):
      WAIT_TIME = int(arg)
   elif opt in ("--pwm-gpio"):
      PWM_GPIO_NR = int(arg)
   elif opt in ("--rpm-gpio"):
      RPM_GPIO_NR = int(arg)
   elif opt in ("--temp-gpio"):
      TEMP_GPIO_NR = int(arg)
   elif opt in ("--pwm-freq"):
      PWM_FREQ = int(arg)
   elif opt in ("--node-exporter"):
      NODE_EXPORTER = 1
   elif opt in ("--cpu"):
      TEMP_SOURCE = 'cpu'
   elif opt in ("--sensor"):
      TEMP_SOURCE = 'sensor'
   elif opt in ("--min-temp-offset"):
      MIN_TEMP_OFFSET = max(int(arg), 0)
   elif opt in ("--min-run-time"):
      MIN_RUN_TIME = max(int(arg), 0)
   elif opt in ("--min-sleep-time"):
      MIN_SLEEP_TIME = max(int(arg), 0)
print("")
print("MIN_TEMP:",MIN_TEMP)
print("MAX_TEMP:",MAX_TEMP)
print("FAN_LOW:",FAN_LOW)
print("FAN_HIGH:",FAN_HIGH)
print("WAIT_TIME:",WAIT_TIME)
print("PWM_GPIO_NR:",PWM_GPIO_NR)
print("RPM_GPIO_NR:",RPM_GPIO_NR)
print("TEMP_GPIO_NR:",TEMP_GPIO_NR)
print("PWM_FREQ:",PWM_FREQ)
print("VERBOSE:",VERBOSE)
print("NODE_EXPORTER:",NODE_EXPORTER)
print("MIN_RUN_TIME:",MIN_RUN_TIME)
print("MIN_SLEEP_TIME:",MIN_SLEEP_TIME)
print("")

# Get CPU's temperature
def getCpuTemperature():
    res = os.popen('cat /sys/devices/virtual/thermal/thermal_zone0/temp').readline()
    temp = (float(res)/1000)
    return temp

# Get temperature from sensor
def getSensorTemperature():
    res = W1ThermSensor().get_temperature()
   #  temp = (float(res)/1000)
    return res

# Set fan speed
def setFanSpeed(speed,temp):
    global currentSpeed
    # update state to reflect current speed
    currentSpeed = speed
    # sbc.tx_pwm(fan , PWM_GPIO_NR, PWM_FREQ, speed, pulse_offset=0, pulse_cycles=0)
    fan.ChangeDutyCycle(speed)
   #  fan.set_PWM_dutycycle(PWM_GPIO_NR, speed)

    # print fan speed and temperature
    if VERBOSE == 1:
        print("fan speed: ",int(speed),"    temp: ",temp)

    # write fan metrics to file for node-exporter/prometheus
    if NODE_EXPORTER == 1:
        # Save a reference to the original standard output
        original_stdout = sys.stdout 
        with open('/var/lib/node_exporter/fan-metrics.prom', 'w') as f:
            # Change the standard output to the file we created.
            sys.stdout = f 
            print('raspberry_fan_speed ',speed)
            print('raspberry_fan_temp ',temp)
            print('raspberry_fan_rpm ',gpio.input(RPM_GPIO_NR))
            print('raspberry_sensor_temp ',getSensorTemperature())
            print('raspberry_fan_min_temp ',MIN_TEMP)
            print('raspberry_fan_max_temp ',MAX_TEMP)
            print('raspberry_fan_fan_low ',FAN_LOW)
            print('raspberry_fan_fan_high ',FAN_HIGH)
            print('raspberry_fan_wait_time ',WAIT_TIME)
            print('raspberry_fan_pwm_gpio ',PWM_GPIO_NR)
            print('raspberry_fana_freq ',PWM_FREQ)
            # Reset the standard output to its original value
            sys.stdout = original_stdout
            f.close()

    return()

# Handle fan speed
def handleFanSpeed():
    global ON_TIME, OFF_TIME

    if TEMP_SOURCE == 'cpu':
      temp = getCpuTemperature()
    elif TEMP_SOURCE == 'sensor':
      temp = getSensorTemperature()

    temp = round(temp)

    # Turn off the fan if temperature is below MIN_TEMP
    if temp < MIN_TEMP:
       # if fan is on and temp within threshold
       if temp > MIN_TEMP - MIN_TEMP_OFFSET and not fanIsOff():
        if VERBOSE == 1:
            print('Temp is not lower than threshold: +', -1 * (MIN_TEMP - temp - MIN_TEMP_OFFSET))
        setFanSpeed(FAN_LOW,temp)

       # temp is lower than threshold, have not elapsed enough time
       elif ON_TIME + MIN_RUN_TIME > now():
        if VERBOSE == 1:
            print('Min run time not met, time remaining: ', ON_TIME + MIN_RUN_TIME - now())
        setFanSpeed(FAN_LOW,temp)

       # turn fan off
       else:
        if not fanIsOff():
            OFF_TIME = now()
            if VERBOSE == 1:
                print('Turning fan off: ', OFF_TIME)
        setFanSpeed(FAN_OFF,temp)

    # Set fan speed to MAXIMUM if the temperature is above MAX_TEMP
    elif temp > MAX_TEMP:
        setFanSpeed(FAN_MAX,temp)

    # Fan has not been off long enough
    elif OFF_TIME + MIN_SLEEP_TIME > now():
        print('Min sleep time not met, time remaining: ', OFF_TIME + MIN_SLEEP_TIME - now())

    # Caculate dynamic fan speed
    else:
        if fanIsOff():
            ON_TIME = now()
            if VERBOSE == 1:
                print('Turning fan on: ', ON_TIME)
        step = (FAN_HIGH - FAN_LOW)/(MAX_TEMP - MIN_TEMP)   
        delta = temp - MIN_TEMP
        speed = FAN_LOW + ( round(delta) * step )
        setFanSpeed(speed,temp)

    return ()

def cleanup():
    setFanSpeed(FAN_LOW,MIN_TEMP)
    fan.stop()
    gpio.cleanup()

atexit.register(cleanup)

try:
    # Setup GPIO pin
    # fan = sbc.gpiochip_open(0)
    gpio.setmode(gpio.BCM)

    gpio.setup(PWM_GPIO_NR, gpio.OUT)
    fan = gpio.PWM(PWM_GPIO_NR, PWM_FREQ)
    fan.start(FAN_LOW)
   #  fan = pigpio.pi()
   #  fan.set_PWM_frequency(PWM_GPIO_NR, PWM_FREQ)

    gpio.setup(RPM_GPIO_NR, gpio.IN)
   #  rpm = gpio.input(RPM_GPIO_NR)

    # sbc.gpio_claim_output(fan, PWM_GPIO_NR)
    setFanSpeed(FAN_OFF,MIN_TEMP)

    # Handle fan speed every WAIT_TIME sec
    while True:
        handleFanSpeed()
        time.sleep(WAIT_TIME)

except KeyboardInterrupt: # trap a CTRL+C keyboard interrupt
    cleanup()
