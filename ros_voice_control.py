#!/usr/bin/env python

"""This module is a simple demonstration of voice control
for ROS turtlebot using pocketsphinx
"""

import argparse
import roslib
import rospy

from geometry_msgs.msg import Twist

from pocketsphinx.pocketsphinx import *
from sphinxbase.sphinxbase import *
import pyaudio

State = {
	"NORMAL": 1,
	"CONFIRM": 2,
	"FAULT": 3
}

Action = {
	"FORWARD": 1,
	"LEFT": 2,
	"BACK": 3,
	"RIGHT": 4,
	"STOP": 5
}

class ASRControl(object):
	"""Simple voice control interface for ROS turtlebot

	Attributes:
		model: model path
		lexicon: pronunciation dictionary
		kwlist: keyword list file
		pub: where to send commands (default: 'mobile_base/commands/velocity')

	"""

	def __init__(self, model, lexicon, kwlist, pub):
		# initialize ROS
		self.speed = 0.1
		self.msg = Twist()

		rospy.init_node('voice_cmd_vel')
		rospy.on_shutdown(self.shutdown)


		self.state = 1
		self.action = 5
		self.oldState = 1
		self.oldAction = 5

		# you may need to change publisher destination depending on what you run
		self.pub_ = rospy.Publisher(pub, Twist, queue_size=10)

		# initialize pocketsphinx
		config = Decoder.default_config()
		config.set_string('-hmm', model)
		config.set_string('-dict', lexicon)
		config.set_string('-kws', kwlist)

		stream = pyaudio.PyAudio().open(format=pyaudio.paInt16, channels=1,
						rate=16000, input=True, frames_per_buffer=1024)
		stream.start_stream()

		self.decoder = Decoder(config)
		self.decoder.start_utt()

		while not rospy.is_shutdown():
			buf = stream.read(1024)
			if buf:
				self.decoder.process_raw(buf, False, False)
			else:
				break
			self.parse_asr_result()

	def parse_asr_result(self):
		"""
		move the robot based on ASR hypothesis
		"""
		if self.state != self.oldState or self.action != self.oldAction:
			self.oldState = self.state
			self.oldAction = self.action
			print "STATE = " + repr(self.state) + "  ACTION = " + repr(self.action)

		if self.decoder.hyp() != None:
			print ([(seg.word, seg.prob, seg.start_frame, seg.end_frame)
				for seg in self.decoder.seg()])
			print ("Detected keyphrase, restarting search")
			seg.word = seg.word.lower()
			self.decoder.end_utt()
			self.decoder.start_utt()

			if self.state == State["NORMAL"]:
				if seg.word.find("forward") > -1:
					self.action = Action["FORWARD"]
					self.state = State["CONFIRM"]
				elif seg.word.find("left") > -1:
					self.action = Action["LEFT"]
					self.state = State["CONFIRM"]
				elif seg.word.find("right") > -1:
					self.action = Action["RIGHT"]
					self.state = State["CONFIRM"]
				elif seg.word.find("back") > -1:
					self.action = Action["BACK"]
					self.state = State["CONFIRM"]
				elif seg.word.find("stop") > -1:
					self.action = Action["STOP"]
					self.state = State["NORMAL"]
					self.msg = Twist()
				else:
					self.state = State["FAULT"]
					self.msg = Twist()
				
			elif self.state == State["CONFIRM"]:
				if seg.word.find("yes") > -1:
					if self.action == Action["FORWARD"]:
						self.msg.linear.x = self.speed
						self.msg.angular.z = 0
						self.state = State["NORMAL"]
						
					if self.action == Action["BACK"]:
						self.msg.linear.x = -self.speed
						self.msg.angular.z = 0
						self.state = State["NORMAL"]
						
					if self.action == Action["LEFT"]:
						if self.msg.linear.x != 0:
							if self.msg.angular.z < self.speed:
								self.msg.angular.z += 0.05
						else:
							self.msg.angular.z = self.speed*2
						self.state = State["NORMAL"]
						
					if self.action == Action["RIGHT"]:
						if self.msg.linear.x != 0:
							if self.msg.angular.z > -self.speed:
								self.msg.angular.z -= 0.05
						else:
							self.msg.angular.z = -self.speed*2
						self.state = State["NORMAL"]
						
				elif seg.word.find("no") > -1:
					#aborting command sequence (___)
					self.state = State["NORMAL"]
				elif seg.word.find("stop") > -1:
					self.action = Action["STOP"]
					self.state = State["NORMAL"]
					self.msg = Twist()
				else:
					#command not confirmed, aborting command sequence
					self.state = State["FAULT"]
					self.msg = Twist()
			else:
				self.msg = Twist()
				self.state = State["NORMAL"]

		self.pub_.publish(self.msg)

	def shutdown(self):
		"""
		command executed after Ctrl+C is pressed
		"""
		rospy.loginfo("Stop ASRControl")
		self.pub_.publish(Twist())
		rospy.sleep(1)

if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		description='Control ROS turtlebot using pocketsphinx.')
	parser.add_argument('--model', type=str,
		default='/usr/local/lib/python2.7/dist-packages/pocketsphinx/model/en-us',
		help='''acoustic model path
		(default: /usr/local/lib/python2.7/dist-packages/pocketsphinx/model/en-us)''')
	parser.add_argument('--lexicon', type=str,
		default='voice_cmd.dic',
		help='''pronunciation dictionary
		(default: voice_cmd.dic)''')
	parser.add_argument('--kwlist', type=str,
		default='voice_cmd.kwlist',
		help='''keyword list with thresholds
		(default: voice_cmd.kwlist)''')
	parser.add_argument('--rospub', type=str,
		default='mobile_base/commands/velocity',
		help='''ROS publisher destination
		(default: mobile_base/commands/velocity)''')

	args = parser.parse_args()
	ASRControl(args.model, args.lexicon, args.kwlist, args.rospub)
