#! /usr/bin/python3

"""

    COPYRIGHT © 2018 BY DATAQ INSTRUMENTS, INC.


!!!!!!!!    VERY IMPORTANT    !!!!!!!!
!!!!!!!!    READ THIS FIRST   !!!!!!!!

This program works only with model DI-1100. 

Disconnect any other instrument models to prevent the program from 
detecting a different device model with a DATAQ Instruments VID and attempting to use it. 
Such attempts will fail.

While the DI-1100's protocol is similar to model DI-2108, it doesn't support
a decimation function. Therefore, its minimum sample rate of ~915 Hz is 
too fast for this program to work properly because of its heavy
use of print statements. The program overcomes that problem 
through use of a 'decimation_factor' variable to slow scan rate to an 
acceptable level. 

The DI-1100 used with this program MUST be placed in its CDC communication mode. 
Follow this link for guidance:
https://www.dataq.com/blog/data-acquisition/usb-daq-products-support-libusb-cdc/

The DI-1100 protocol this program uses can be downloaded from the instrument's 
product page:
https://www.dataq.com/resources/pdfs/misc/di-1100-protocol.pdf
"""


import serial
import serial.tools.list_ports
import keyboard
import time
import glob
""" 
Example slist for model DI-1100
0x0000 = Analog channel 0, ±10 V range
0x0001 = Analog channel 1, ±10 V range
0x0002 = Analog channel 2, ±10 V range
0x0003 = Analog channel 3, ±10 V range

"""
slist = [0x0000,0x0001,0x0002,0x0003]

ser=serial.Serial()

"""
Since model DI-1100 cannot scan slower that 915 Hz at the protocol level, 
and that rate or higher is not practical for this program, define a decimation 
factor to slow scan rate to a practical level. It defines the number of analog readings to average
before displaying them. By design, digital input values display instantaneously
without averaging at the same rate as decimated analog values.

Averaging n values on each analog channel is more difficult than simply using
every nth value, but is recommended since it reduces noise by a factor of n^0.5 

'decimation_factor' must be an integer value greater than zero. 
'decimation_factor' = 1 disables decimation and attemps to output all values.
"""


# Define flag to indicate if acquiring is active 
acquiring = False

""" Discover DATAQ Instruments devices and models.  Note that if multiple devices are connected, only the 
device discovered first is used. We leave it to you to ensure that it's a DI-1100."""
def discovery():
    # Get a list of active com ports to scan for possible DATAQ Instruments devices
    available_ports = list(serial.tools.list_ports.comports())
    #print(available_ports)
    # Will eventually hold the com port of the detected device, if any
    hooked_port = "" 
    #temp_list = glob.glob ('/dev/tty[A-Za-z]*')
    #result = []
    #for a_port in temp_list:

    #    try:
    #        s = serial.Serial(a_port)
    #        s.close()
    #        result.append(a_port)
    #    except serial.SerialException:
    #        pass

    #print(result)

    for p in available_ports:
        # Do we have a DATAQ Instruments device?
        #print(p.hwid)
        if ("VID:PID=0683" in p.hwid):
            # Yes!  Dectect and assign the hooked com port
            hooked_port = p.device
            break

    if hooked_port:
        #print("Found a DATAQ Instruments device on",hooked_port)
        ser.timeout = 0
        ser.port = hooked_port
        ser.baudrate = '115200'
        ser.open()
        return(True)
    else:
        # Get here if no DATAQ Instruments devices are detected
        print("Please connect a DATAQ Instruments device")
        input("Press ENTER to try again...")
        return(False)

# Sends a passed command string after appending <cr>
def send_cmd(command):
    ser.write((command+'\r').encode())
    time.sleep(.1)
    if not(acquiring):
        # Echo commands if not acquiring
        while True:
            if(ser.inWaiting() > 0):
                while True:
                    try:
                        s = ser.readline().decode()
                        s = s.strip('\n')
                        s = s.strip('\r')
                        s = s.strip(chr(0))
                        break
                    except:
                        continue
                if s != "":
                    #print (s)
                    break

def return_O2(ser,decimation_factor,achan_accumulation_table):

    dec_count = decimation_factor
    slist_pointer = 0
    # Init the logical channel number for enabled analog channels
    achan_number = 0
    output_string = ''
    while dec_count!=0:
        while (ser.inWaiting() > (2 * len(slist))):
            for i in range(len(slist)):
                # Always two bytes per sample...read them
                bytes = ser.read(2)
                # Only analog channels for a DI-1100, with dig_in states appearing in the two LSBs of ONLY the first slist position
                result = int.from_bytes(bytes,byteorder='little', signed=True)
                #print("dc: {}".format(dec_count))
                # Since digital input states are embedded into the analog data stream there are four possibilities:
                if (dec_count == 1) and (slist_pointer == 0):
                    # Decimation loop finished and first slist position
                    # Two LSBs carry information only for first slist posiiton. So, ...
                    # Preserve lower two bits representing digital input states
                    dig_in = result & 0x3
                    # Strip two LSBs from value to be added to the analog channel accumulation, preserving sign
                    result = result >> 2
                    result = result << 2
                    # Add the value to the accumulator
                    achan_accumulation_table[achan_number] = result + achan_accumulation_table[achan_number]
                    achan_number += 1
                    # End of a decimation loop. So, append accumulator value / decimation_factor  to the output string
                    output_string = output_string + "{: 3.3f} ".format(achan_accumulation_table[achan_number-1] * 10 / 32768 / decimation_factor /4*100)

                elif (dec_count == 1) and (slist_pointer != 0):
                    # Decimation loop finished and NOT the first slist position
                    # Two LSBs carry information only for first slist posiiton, which this isn't. So, ...
                    # Just add value to the accumulator
                    achan_accumulation_table[achan_number] = result + achan_accumulation_table[achan_number]
                    achan_number += 1
                    # End of a decimation loop. So, append accumulator value / decimation_factor  to the output string
                    output_string = output_string + "{: 3.3f} ".format(achan_accumulation_table[achan_number-1] * 10 / 32768 / decimation_factor /4*100)

                elif (dec_count != 1) and (slist_pointer == 0):
                    # Decimation loop NOT finished and first slist position
                    # Not the end of a decimation loop, but this is the first position in slist. So, ...
                    # Just strip two LSBs, preserving sign...
                    result = result >> 2
                    result = result << 2
                    # ...and add the value to the accumulator
                    achan_accumulation_table[achan_number] = result + achan_accumulation_table[achan_number]
                    achan_number += 1
                else:
                    # Decimation loop NOT finished and NOT first slist position
                    # Nothing to do except add the value to the accumlator
                    achan_accumulation_table[achan_number] = result + achan_accumulation_table[achan_number]
                    achan_number += 1

                # Get the next position in slist
                slist_pointer += 1

                if (slist_pointer + 1) > (len(slist)):
                    # End of a pass through slist items
                    if dec_count == 1:
                        # Get here if decimation loop has finished
                        dec_count = decimation_factor
                        # Reset analog channel accumulators to zero
                        achan_accumulation_table = [0] * len(achan_accumulation_table)
                        # Append digital inputs to output string
                        output_string = output_string 
                        print(output_string) 
                        return output_string
                        #output_string = ""
                    else:
                        dec_count -= 1             
                    slist_pointer = 0
                    achan_number = 0
    #print(output_string)
    return output_string

# Configure the instrment's scan list
def config_scn_lst(achan_accumulation_table):
    # Scan list position must start with 0 and increment sequentially
    position = 0
    for item in slist:
        send_cmd("slist "+ str(position ) + " " + str(item))
        # Add the channel to the logical list.
        achan_accumulation_table.append(0)
        position += 1

while discovery() == False:
    discovery()

if __name__ == "__main__":
    # Define a decimation factor variable
    decimation_factor = 100 #was 1000

    # Contains accumulated values for each analog channel used for the average calculation
    achan_accumulation_table = list(())

    # Stop in case DI-1100 is already scanning
    send_cmd("stop")
    # Define binary output mode
    send_cmd("encode 0")
    # Keep the packet size small for responsiveness
    send_cmd("ps 0")
    # Configure the instrument's scan list
    config_scn_lst(achan_accumulation_table)

    # Define sample rate = 1 Hz, where decimation_factor = 1000:
    # 60,000,000/(srate) = 60,000,000 / 60000 / decimation_factor = 1 Hz
    send_cmd("srate 60000")

    # This is the slist position pointer. Ranges from 0 (first position)
    # to len(slist)
    slist_pointer = 0

    # Init a decimation counter:
    dec_count = decimation_factor

    # This is the constructed output string
    output_string = ""

    # This is the main program loop, broken only by typing a command key as defined
    acquiring = True
    send_cmd("start")

    return_O2(ser, dec_count, achan_accumulation_table)

    ser.close()
    SystemExit



