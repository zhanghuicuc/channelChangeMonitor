#!/usr/bin/python
#coding:utf-8


###
# This script can change live channels automatically and calculate related stats
# Author:
# zhang hui <zhanghui9@le.com;zhanghuicuc@gmail.com>
# LeEco BSP Multimedia / Communication University of China

###Basic Design Idea is as follows:
'''
input device ip, change times and interval
do the change and read log to collect stats
stuct channelChangeStat{
	releaseTime
	prepareTime
	startTime
	overallTime
}
output stats
'''


import os
import sys
import subprocess
import time
import commands
import Queue
import threading
from optparse import OptionParser
from time import sleep
from subprocess import check_output, CalledProcessError

Stats = []

class Stat:
    def __init__(self):
        #self.changeId = changeId
        self.resetTime = 0
        self.disconnectTime = 0
        self.constructTime = 0
        self.startTime = 0

    def getReleaseTime(self):
        return self.disconnectTime - self.resetTime

    def getPrepareTime(self):
        return self.constructTime - self.disconnectTime

    def getStartTime(self):
        return self.startTime - self.constructTime

    def getOverallTime(self):
        return self.startTime - self.resetTime

    def setResetTime(self, resetTime):
        self.resetTime = resetTime

    def setDisconnectTime(self, disconnectTime):
        self.disconnectTime = disconnectTime

    def setConstructTime(self, constructTime):
        self.constructTime = constructTime

    def setStartTime(self, startTime):
        self.startTime = startTime

    def copyFrom(self, stat):
        self.resetTime = stat.resetTime
        self.disconnectTime = stat.disconnectTime
        self.constructTime = stat.constructTime
        self.startTime = stat.startTime

class AsynchronousFileReader(threading.Thread):
    '''
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    '''

    def __init__(self, fd, queue):
        assert isinstance(queue, Queue.Queue)
        assert callable(fd.readline)
        threading.Thread.__init__(self)
        self._fd = fd
        self._queue = queue

    def run(self):
        '''The body of the thread: read lines and put them on the queue.'''
        for line in iter(self._fd.readline, ''):
            self._queue.put(line)

    def eof(self):
        '''Check whether there is no more content to expect.'''
        return not self.is_alive() and self._queue.empty()

def run_command(options, cmd):
    if options.debug:
        print 'COMMAND: ', cmd
    try:
        out_bytes = subprocess.check_output(cmd, shell=True)
        out_text = out_bytes.decode('utf-8')
        if options.debug:
            print out_text
        return out_text
    except CalledProcessError, e:
        message = "binary tool failed with error %d" % e.returncode
        if options.verbose:
            message += " - " + str(cmd)	 
        raise Exception(message)

def connect_device(options, ip):
    cmd = 'adb connect ' + ip
    result = run_command(options, cmd)
    if ("unable" in result):
        sys.exit("Connect Device Failed!")
    else:
        print 'Connect Device Success'

#parse log to get time (ms)
def parse_line(options, line):
    #something like 11-16 16:27:05.614  2953  2953 I SpoPlayer: [3] disconnect done
    line = line.rstrip()
    dates = line.split(' ')
    timeMs = dates[1]
    if options.debug:
        print timeMs
    timeMs = timeMs.split(':')
    hour = (long)(timeMs[0])
    if options.debug:
        print hour
    minute = (long)(timeMs[1])
    if options.debug:
        print minute
    seconds = timeMs[2].split('.')
    second = (long)(seconds[0])
    if options.debug:
        print second
    millisecond = (long)(seconds[1])
    if options.debug:
        print millisecond
    millisecond = (hour*3600*1000 + minute*60*1000 + second*1000 + millisecond)
    if options.debug:
        print millisecond
    return millisecond

if __name__=='__main__':
    parser = OptionParser(usage="%prog -d -p pid -t interval")
    parser.add_option('-d', '--debug', dest="debug", action='store_true', default=False,
                          help="Print out debugging information")
    parser.add_option('-i', '--ip', dest="device_ip",
                          help="Device IP")
    parser.add_option('-t', '--times', dest="change_times",
                          help="How many times do you want to change channel")
    parser.add_option('-r', '--interval', dest="change_interval",
                          help="Time interval for channel changing, in seconds ex.(1.5 means 1500ms)")
    (options, args) = parser.parse_args()
    if options.device_ip:
        Ip = options.device_ip
        connect_device(options, Ip)
    if options.change_times:
        Times = (int)(options.change_times)
    if options.change_interval:
        Interval = (float)(options.change_interval)

    #go home three times, make sure we are at home
    homeCmd = 'adb shell input keyevent KEYCODE_HOME'
    run_command(options, homeCmd)
    run_command(options, homeCmd)
    run_command(options, homeCmd)
    print 'We are at home now'
    sleep(3)

    # You'll need to add any command line arguments here.
    process = subprocess.Popen("adb logcat -s SpoPlayer", stdout=subprocess.PIPE, shell=True)

    # Launch the asynchronous readers of the process' stdout.
    stdout_queue = Queue.Queue()
    stdout_reader = AsynchronousFileReader(process.stdout, stdout_queue)
    stdout_reader.start()

    changeCmd = 'adb shell input keyevent KEYCODE_CHANNEL_UP'
    i = 0
    changeDate = 0
    stat = Stat()
    # Check the queues if we received some output (until there is nothing more to get).
    while not stdout_reader.eof():
        while not stdout_queue.empty():
            line = stdout_queue.get()
            if ("reset" in line):
                if options.debug:
                    print line
                resetTime = parse_line(options, line)
                stat.setResetTime(resetTime)
            if ("disconnect" in line):
                if options.debug:
                    print line
                disconnectTime = parse_line(options, line)
                stat.setDisconnectTime(disconnectTime)
            if ("construct" in line):
                if options.debug:
                    print line
                constructTime = parse_line(options, line)
                stat.setConstructTime(constructTime)
            if ("render start" in line):
                if options.debug:
                    print line
                startTime = parse_line(options, line)
                stat.setStartTime(startTime)
                stat_save = Stat()
                stat_save.copyFrom(stat)
                Stats.append(stat_save)
            if ((i == 0) or ((time.time() - changeDate >= Interval) and (i < Times))):
                print 'Change Channel %d Times!' % ((int)(i+1))
                run_command(options, changeCmd)
                changeDate = time.time()
                if options.debug:
                    print 'change date:', changeDate
                i = i + 1
            if ((i == Times) and (time.time() - changeDate >= Interval)):
                break
        if ((i == Times) and (time.time() - changeDate >= Interval)):
            break

    print 'Stats:'
    print 'No.  releaseTime prepareTime startTime overallTime'
    releaseTimeAvg = 0
    prepareTimeAvg = 0
    startTimeAvg = 0
    overallTimeAvg = 0
    for i in range(len(Stats)):
        if(Stats[i].getReleaseTime() > 0):
            print '%2d      %4d        %4d        %4d        %4d' % (i, Stats[i].getReleaseTime(), Stats[i].getPrepareTime(), Stats[i].getStartTime(), Stats[i].getOverallTime())
            releaseTimeAvg = releaseTimeAvg + Stats[i].getReleaseTime()
            prepareTimeAvg = prepareTimeAvg + Stats[i].getPrepareTime()
            startTimeAvg = startTimeAvg + Stats[i].getStartTime()
            overallTimeAvg = overallTimeAvg + Stats[i].getOverallTime()
    print 'avg     %4d        %4d        %4d        %4d' % (releaseTimeAvg/len(Stats), prepareTimeAvg/len(Stats), startTimeAvg/len(Stats), overallTimeAvg/len(Stats))

    sys.exit("Finished")
