#--------------------------------------------------------------------
#               Airspan CPE Telnet Script
#
#   Purpose:    To obtain CPE information (RSSI, CINR, etc..) through
#               local Telnet connection with CLI commands and send
#               the data to the Syslog remote server(s)
#--------------------------------------------------------------------

#***************header files***************
import threading
import telnetlib
import time
import datetime
import syslog
import string
import commands

#==============================
#----------Management----------
#------------------------------

#Status Extraction Interval
loop_time = 5

#CPE local IP address
cpe_host = "10.1.1.254"

#Login name and password ("airspan" & "@dj/#fu4")
cpe_user = b"airspan\n"
cpe_password = b"@dj/#fu4\n"

#timeout set for each CLI command in case of program hang on bad Link
cpe_timeout = 10

#Syslog Facility
facility = 0

#==============================
#----------Log Stats-----------
#------------------------------

#Commands that returns information we need
#(refer to CLI reference manual)
cmds = [
    "showTime",
    "showPhyStats",
    "showRfTx",
    "showSs"
    ]

#Columns in the command feedback that we are interested in logging
#
#For example:   Current time (s) in showTime
#               RSSI (dBm) and CINR (dB) in showSsPhyStats
#
#NOTE:  the column name needs to match what is returned from the CPE
cols = [
    "Current time (s)",
    "RSSI (dBm),CINR (dB),CINR Reuse 1 (dB),CINR Reuse 3 (dB),Zone CINR channel 0 (dB)",
    "Frequency (kHz)",
    "state,current fec-code,current grant fec-code,BS ID"
    ]

#Readable Column names for syslog message titles
titles = [
    "Uptime (s)",
    "RSSI(dBm),CINR(dB),CINR Reuse 1(dB),CINR Reuse 3(dB),Zone CINR channel 0(dB)",
    "Frequency(kHz)",
    "State,Downlink Modulation,Uplink Modulation,BSID"
    ]

#==============================

#--------------------------------------------------------------------
#   Function:   cpemimaxpro
#   Purpose:    Acquire the feedback from CPE
#   Parameters: cmd - CLI command
#   Return:     Feedback strings
#   Programmer: Peter Chen
#--------------------------------------------------------------------

def cpemimaxpro(cmd):

    try:
        tn.write(b"cbe \""+cmd+b"\"\n")
        t = tn.read_until("->".encode(),cpe_timeout)
    except StandardError:
        return False
    else:
        if t == " ":
            return False
        else:
            return t

#--------------------------------------------------------------------
#   Function:   decode
#   Purpose:    To organize the string sent back from the CPE, and get
#               valuable information
#   Parameters: data - data string (comma separated)
#               col - interested variables (comma separated)
#               string - feedback string from the CPE
#   Return:     data - data string (comma separated)
#   Programmer: Peter Chen
#--------------------------------------------------------------------

def decode(col, string):

    #Initialized
    data = ""
    i = True
    
    #split the column string by comma
    col_array = col.split(",")

    #convert bytes array to a string
    string = string.decode("utf-8")

    #Split the string by the next line (\r\n) command
    string_array = string.split("\r\n")
    
    for col_items in col_array:

        data_temp = "N/A"

        #Examine line by line
        for string_items in string_array:

            #Split each line by ": " to separate the variables and values
            string_value = string_items.split(": ")

            if len(string_value) == 2:

                if string_value[1] != "":

                    #Remove duplicated spaces at the beginning and at the end
                    col_temp = " ".join(string_value[0].strip().split())

                    #record down the values of our interested variables
                    if col_temp == col_items:
                        data_temp = string_value[1].strip()
                        break

        if i:
            data = data_temp
            i = False
        else:
            data = data + "," + data_temp
            
    return data

#--------------------------------------------------------------------
#   Function:   writesyslog
#   Purpose:    To output message via syslog
#   Parameters: local - integer of which local facility to use (0-7)
#                       0   CPE Status
#                       1   N/A
#                       2   N/A
#                       3   N/A
#                       4   N/A
#                       5   N/A
#                       6   N/A
#                       7   N/A
#               severity - integer of the severity level (0-7)
#                          0    Emergency
#                          1    Alert
#                          2    Critical
#                          3    Error
#                          4    Warming
#                          5    Notice
#                          6    Informational
#                          7    Debug
#               message - message string 
#   Return:     data - data string (comma separated)
#   Programmer: Peter Chen
#--------------------------------------------------------------------

def writesyslog(local, severity, message):

    if local == 0:
        syslog.openlog(facility=syslog.LOG_LOCAL0)
    elif local == 1:
        syslog.openlog(facility=syslog.LOG_LOCAL1)
    elif local == 2:
        syslog.openlog(facility=syslog.LOG_LOCAL2)
    elif local == 3:
        syslog.openlog(facility=syslog.LOG_LOCAL3)
    elif local == 4:
        syslog.openlog(facility=syslog.LOG_LOCAL4)
    elif local == 5:
        syslog.openlog(facility=syslog.LOG_LOCAL5)
    elif local == 6:
        syslog.openlog(facility=syslog.LOG_LOCAL6)
    elif local == 7:
        syslog.openlog(facility=syslog.LOG_LOCAL7)

    if severity == 0:
        syslog.syslog(syslog.LOG_EMERG,message)
    elif severity == 1:
        syslog.syslog(syslog.LOG_ALERT,message)
    elif severity == 2:
        syslog.syslog(syslog.LOG_CRIT,message)
    elif severity == 3:
        syslog.syslog(syslog.LOG_ERR,message)
    elif severity == 4:
        syslog.syslog(syslog.LOG_WARNING,message)
    elif severity == 5:
        syslog.syslog(syslog.LOG_NOTICE,message)
    elif severity == 6:
        syslog.syslog(syslog.LOG_INFO,message)
    elif severity == 7:
        syslog.syslog(syslog.LOG_DEBUG,message)

    syslog.closelog()
    
#--------------------------------------------------------------------
#********************************************************************
#####################################################################
#********************************************************************
#--------------------------------------------------------------------

#***************Main Function***************
#
#   Programer:  Peter Chen
#
#*******************************************
                
if __name__ == '__main__':

    Loop = True
    num = len(cols)

    cols_check = ",".join(cols).split(",")

    title_array = ",".join(titles).split(",")

    if len(cols) == len(cmds) and len(cols_check) == len(title_array):
        
        print("Script START")

        try:
            while Loop:

                #Reset
                message = ""
                data_array = []
                
                #message severity - informational (6)
                severity = 6

                #Check Ethernet Adaptor Status on Pi
                Link = False
                check = commands.getoutput("sudo ethtool eth0 | grep Link")
                check_array = check.strip().split("\n\t")
                for check_items in check_array:
                    check_temp = check_items.strip().split(": ")
                    if check_temp[0] == "Link detected":
                        if check_temp[1] == "yes":
                            Link = True

                #If eth0 is up and running
                if Link:
                
                    try:

                        #Open the telnet port (23)
                        tn = telnetlib.Telnet(cpe_host,23,cpe_timeout)

                    except StandardError:
                        
                        #preparing a syslog Error message
                        message = "CLI Telnet Error - CPE ("+ cpe_host +") unreachable from Raspberry Pi"
                        #message severity - Error (3)
                        severity = 3

                    else:
                        
                        #Read until "login: " then enter the username
                        tn.read_until("login: ".encode(),cpe_timeout)
                        tn.write(cpe_user)

                        #Read until "Password: " then enter the password
                        tn.read_until("Password: ".encode(),cpe_timeout)
                        tn.write(cpe_password)

                        #Read until "->" to start sending commands and acquiring data
                        tn.read_until("->".encode(),cpe_timeout)
                        
                        for i in range(0, num):

                            #Send command to the CPE
                            string = cpemimaxpro( cmds[i] )
                            
                            if string:
                                #Decode the information
                                temp = decode( cols[i], string )
                                data_array.append( str(temp) )
                            else:
                                #message severity - Warning (4)
                                severity = 4
                                for col in cols[i].split(","):
                                    data_array.append( str("Not Accessible") )
                                                  
                        #Close the Telnet connection
                        tn.close()
                        
                        data_items = ",".join(data_array).split(",")
                        
                        #Preparing a syslog message entry
                        i = 0
                        for title_items in title_array:
                            message = message + title_items + ": " + data_items[i]
                            if i != len(title_array)-1:
                                message = message + ",    "
                            i = i + 1

                #if eth0 is down
                else:
                    
                    #preparing a syslog Error message
                    message = "Ethernet Adaptor Error - Raspberry Pi eth0 is down"
                    #message severity - Error (3)
                    severity = 3

                #print(message)    
                writesyslog(facility,severity,message)
                
                #delay interval
                time.sleep(loop_time)
                
        except KeyboardInterrupt:
            Loop = False
    else:
        print("Error: cols and cmds, or cols and titles mismatch. Please edit the script and start again")

    print("Script STOP")
        
#***************End of Script***************
