# MARCDRED'S MACT_TO_CAT.py V4.2 #
# marcdred@outlook.com #
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
	from typing_extensions import Self
import struct
from dataclasses import dataclass
import math
import numpy
from itertools import chain
import os
import sys
from pathlib import Path
import time
from copy import deepcopy

# GOALS:
# --	Slightly decrease param type dependency to template files.
# --	Add optimization to TRACKS so that files are smaller and you can have more of them without breaking the game.
# --	Improve error handling/debugging.

## SETTINGS ##
bool_print_debug = False
bool_print_tree = False
bool_little_endian = True
bool_enable_param_optimization = False
# (slow optimization seems to never be worth it, takes 10x as long to improve 20% best case)
bool_quick_param_optimization = True


## CLASSES ##
@dataclass
class ActNode:
	keywords: list[str]
	children: list[Self]

	def print_tree(self):
		self._print_tree(0)

	def _print_tree(self, level):
		my_string = ntabs(level)
		my_string += str(self.keywords)
		print(my_string)
		for c in self.children:
			c._print_tree(level+1)

	def write_tree(self, file):
		self._write_tree(file, 0)

	def _write_tree(self, file, level):
		my_string = ntabs(level)
		my_string += str(self.keywords)
		my_string += "\n"
		file.write(my_string)
		for c in self.children:
			c._write_tree(file, level+1)


@dataclass
class OffsetManager:
	sleeping_strings: list[SleepingString]
	sleeping_groups: list[SleepingGroup]
	sleeping_reference_strings: list[SleepingString]
	sleeping_conditions: list[SleepingLogic]
	sleeping_group_conditions: list[SleepingLogic]
	sleeping_tracks: list[SleepingLogic]

	debug_merged_strings: int = 0
	debug_merged_logic: int = 0
	debug_merged_groups: int = 0

	def _add_sleeping_string(self, new_ss, sleeper_list):
		repeated = False
		for old_ss in sleeper_list:
			if old_ss.string == new_ss.string:
				repeated = True
				for v in new_ss.string_users:
					old_ss.string_users.append(v)
				for v in new_ss.string_slots:
					old_ss.string_slots.append(v)
				for v in new_ss.param_slots:
					old_ss.param_slots.append(v)
				for v in new_ss.param_offsets:
					old_ss.param_offsets.append(v)
				self.debug_merged_strings += 1
				break
		if not repeated:
			sleeper_list.append(new_ss)

	def add_sleeping_string(self, new_ss):
		self._add_sleeping_string(new_ss, self.sleeping_strings)

	def add_sleeping_reference_string(self, new_srs):
		self._add_sleeping_string(new_srs, self.sleeping_reference_strings)

	def _add_sleeping_group(self, new_sg, sleeper_list):
		repeated = False
		for old_sg in sleeper_list:
			if old_sg.cg_param == new_sg.cg_param:
				repeated = True
				for v in new_sg.cg_users:
					old_sg.cg_users.append(v)
				for v in new_sg.group_slots:
					old_sg.group_slots.append(v)
				for v in new_sg.condition_slots:
					old_sg.condition_slots.append(v)
				for v in new_sg.condition_offsets:
					old_sg.condition_offsets.append(v)
				for v in new_sg.param_slots:
					old_ss.param_slots.append(v)
				for v in new_sg.param_offsets:
					old_ss.param_offsets.append(v)
				self.debug_merged_groups += 1
				break
		if not repeated:
			sleeper_list.append(new_sg)

	def add_sleeping_group(self, new_sg):
		self._add_sleeping_group(new_sg, self.sleeping_groups)

	def _add_sleeping_logic(self, new_sl, sleeper_list, allow_repeated):
		repeated = False
		if not allow_repeated:
			for old_sl in sleeper_list:
				if old_sl.logic == new_sl.logic:
					repeated = True
					for v in new_sl.logic_slots:
						old_sl.logic_slots.append(v)
					self.debug_merged_logic += 1
					break
		if not repeated:
			sleeper_list.append(new_sl)

	def add_sleeping_condition(self, new_sc, allow_repeated=False):
		self._add_sleeping_logic(new_sc, self.sleeping_conditions, allow_repeated)

	def add_sleeping_group_condition(self, new_sgc, allow_repeated=False):
		self._add_sleeping_logic(new_sgc, self.sleeping_group_conditions, allow_repeated)

	def add_sleeping_track(self, new_st, allow_repeated=False):
		self._add_sleeping_logic(new_st, self.sleeping_tracks, allow_repeated)


@dataclass
class CounterManager:
	counterA: int = 0
	counterB: int = 0
	counterC: int = 0
	counterD: int = 0


@dataclass
class SleepingString:
	# main
	string: str
	string_users: list[LogicNode]
	# used by variable table
	string_slots: list[int] # multiple string slots required because of 'FileReference'
	# used by params when writing param data
	param_slots: list[int]
	param_offsets: list[int]


@dataclass
class SleepingGroup:
	# MAP:
	# [GROUP VARIABLES]
	# [X] LIST OF GROUP VARIABLES --> GROUP VARIABLE
	# [GROUP VARIABLE]
	# [X]	GROUP SLOTS --> GROUP
	# [X]	PARAMETER SLOTS --> PARAMETER
	# [GROUP]
	# [X] CONDITION OFFSETS --> CONDITION
	#
	# CG_PARAM:
	# LogicNode structure that contains a param with type condition group.
	cg_param: LogicNode
	cg_users: list[LogicNode]
	# GROUP_SLOT_OFFSETS:
	# List of <integer offsets> stored in <GROUP VARIABLES>
	# that point to a group.
	# This list is created when
	# This list will be filled when running write_groups()
	group_slots: list[int]
	# CONDITION_SLOT_OFFSETS:
	# List of <integer offsets> stored in <GROUP>
	# that point to a condition.
	# This list is created when running write_groups()
	condition_slots: list[int]
	condition_offsets: list[int]
	# PARAM_SLOT_OFFSETS:
	# List of <integer offsets> stored in <GROUP VARIABLES>
	# that point to a parameter.
	# This list is created when running write_group_variables()
	param_slots: list[int]
	param_offsets: list[int]


@dataclass
class SleepingLogic:
	logic: LogicNode
	logic_slots: list[int]
	logic_offset: int


@dataclass
class LogicOptimization:
	sleeping_logic: SleepingLogic
	optimization: OptimizationMatch


@dataclass
class DbLogic:
	title: str
	params: list[DbParam]


@dataclass
class DbParam:
	id: int
	title: str
	type: str


@dataclass
class LogicNode:
	title: str
	type: str
	value: str
	value_type: str
	conditions: list[LogicNode]
	tracks: list[LogicNode]
	params: list[LogicNode]
	children: list[LogicNode]

	def print_tree(self):
		self._print_tree(0)

	def _print_tree(self, level):
		my_string = ndots(level)
		my_string += "{0} ({1}), {2} ({3}), CD: {4}, TR: {5}, PS: {6}, C: {7}".format(self.title, self.type,
																					  self.value, self.value_type, len(self.conditions), len(self.tracks), len(self.params), len(self.children))
		print(my_string)
		for c in self.children:
			c._print_tree(level+1)


## FUNCTIONS ##
def ntabs(n):
	return n*"\t"


def ndots(n):
	return n*"."


def split_string(string, pos):
	return string[:pos], string[pos:]


def strip_string(string):
	# Remove quotes if any
	if string.startswith('\"'):
		string = string[1:-1]
	if string.startswith('h\"'):
		string = string[2:-1]
	return string


def print_debug(msg):
	if bool_print_debug:
		print(msg)


def _to_int32(val):
	return numpy.array((val,), dtype=numpy.int32)


def _hash_cat_string(string, type):
	string = string.upper()
	result = _to_int32(0)

	for c in string:
		result *= 0x83
		result += ord(c)

	# required for all
	result = result & 0x7FFFFFFF
	# enable this for (branch/bank/node titles) ((Bank Nemesis, Node Purchase))
	# disable this for (track/condition name/value and params/value) ((Track Animation, "C_PLAYER\PICKUP"))
	if type:
		result = result | 0x80000000

	result = hex(int(result))
	# pad and flip endian
	old_result = result[2:]
	if len(old_result) < 8:
		old_result = "0"*(8-len(old_result)) + old_result
	new_result = "00000000"
	new_result = list(new_result)
	for i in range(0, 8, 2):
		new_result[6-i] = old_result[i]
		new_result[6-i+1] = old_result[i+1]
	final_result = "0x"
	for c in new_result:
		final_result += c
	return final_result


def format_write(file, variable, format):
	if bool_little_endian:
		format = "<" + format
	else:
		format = ">" + format
	if isinstance(variable, str):
		variable = bytes(variable, 'utf-8')
	value = struct.pack(format, variable)
	file.write(value)
	return


def hash_cat_title(string):
	result = _hash_cat_string(string, 1)
	result = result[2:]
	result = bytearray.fromhex(result)
	return result


def hash_cat_value(string):
	result = _hash_cat_string(string, 0)
	result = result[2:]
	result = bytearray.fromhex(result)
	return result


def get_value_type(value):
	# Decide value type
	if value is None:
		return "none"
	elif value.startswith("0x") and len(value) > 4:
		return "bytes"
	elif value.startswith("0x") and len(value) <= 4:
		return "bool"
	elif value.upper() == "TRUE" or value.upper() == "FALSE":
		return "bool"
	elif value.startswith('\"') or value.startswith('\''):
		return "string"
	elif value.startswith("h\"") or value.startswith("h\'"):
		return "hashed_string"
	elif '.' in value:
		return "float"
	else:
		return "int"


def generate_keyword_tree(lines):
	# remove empty lines
	bad_characters = ('', ' ', '\t', '\0', '\r', '\r', '\n')
	good_lines = []
	for i, l in enumerate(lines):
		good_line = False
		for c in l:
			if c not in bad_characters:
				good_line = True
		if good_line:
			good_lines.append((i, l))
	# call real parsing
	_, tree, _ = _generate_keyword_tree(good_lines, [], [], 0)
	if len(tree) == 1:
		return tree[0]
	else:
		print("Warning: Unexpected number of roots in act tree.")
		return tree


def _generate_keyword_tree(enumerated_lines, local_logics, global_logics, logic_level):
	# Generate tree using curly brackets
	line_id = enumerated_lines[0][0]
	raw_line = enumerated_lines[0][1]
	enumerated_lines = enumerated_lines[1:]
	# Manage keywords without changing raw_line
	keywords = []
	kw_start = 0
	kw_breaks = []
	kw_end = 0
	# Count tabs in line
	tab_level = -1
	# Manage logic
	state_quote = False
	state_space = False
	state_end_of_line = False
	print_debug("{0} debug: Line ID '{1}', '{2}'.".format(
		ntabs(logic_level), line_id, raw_line.strip()))
	for i, c in enumerate(raw_line):
		# Beware: 'i' is no longer accurate after changing raw_line
		# Calculate tab level and skip to start of string
		if tab_level < 0:
			if c == ' ':
				print("{0} Warning: Whitespace character ' ' used for identation on line {1}, position {2}.".format(
					ntabs(logic_level), line_id, i))
				continue
			if c == '\t':
				continue
			else:
				tab_level = i
				kw_start = i
		# completely ignore \r characters
		# i hope this is enough for windows support
		if c == '\r':
			continue
		# state_quote will prevent strings in quotes from getting
		# cut short by whitespace characters and '#'
		if not state_quote:
			# Break string if # (for comments)
			if c == '#':
				kw_end = i
				break
			# Check for space between words
			# Split string and remove excessive spaces
			whitespace_characters = ('\t', ' ')
			if c in whitespace_characters:
				# print("Character: '{0}' at {1}".format(c, i))
				kw_breaks.append(i)
		# String between quotes must be preserved entirely (with spaces)
		# warning: for now " and ' are treated as same character
		if c == '\"' or c == '\'':
			state_quote = not state_quote
		# End of line logic
		if (c == '\n') and not state_end_of_line:
			# state_end_of_line wil prevent lines with singular '{' and '}'
			# from getting added to the keywords list
			state_end_of_line = True
			kw_end = i
			final_keywords = []
			if not len(kw_breaks):
				# No whitespaces, return stripped keyword
				# If keyword is size 1, return character as keyword
				if kw_start == kw_end:
					keyword = c
				else:
					keyword = raw_line[kw_start:kw_end]
				if len(keyword):
					final_keywords.append(keyword)
			else:
				# Break whitespaces into separate stripped keywords
				for i, b in enumerate(kw_breaks):
					first_half, second_half = split_string(raw_line, b)
					second_half = second_half[1:-1]
					if i == 0:
						first_half = first_half[kw_start:]
					if i == len(kw_breaks):
						second_half = second_half[:kw_end]
					if len(first_half):
						final_keywords.append(first_half)
					if len(second_half):
						final_keywords.append(second_half)
			for kw in final_keywords:
				keywords.append(kw)
			my_logic = ActNode(keywords, [])
			local_logics.append(my_logic)
			global_logics.append(my_logic)
		# Curly bracket logic
		if c == '{':
			state_end_of_line = True
			last_logic = global_logics[-1]
			if last_logic:
				print_debug("{0} debug: Curly bracket recursion.".format(
					ntabs(logic_level)))
				enumerated_lines, children, global_logics = _generate_keyword_tree(
					enumerated_lines, [], global_logics, logic_level+1)
				for c in children:
					last_logic.children.append(c)
			else:
				print("{0} Warning: Unexpected left curly bracket '{{' on line {1}, position {2}.".format(
					ntabs(logic_level), line_id, i))
		if c == '}':
			print_debug("{0} debug: Closing curly bracket.".format(
				ntabs(logic_level)))
			return enumerated_lines, local_logics, global_logics
	if not len(enumerated_lines):
		print_debug("{0} debug: No more lines in file.".format(
			ntabs(logic_level)))
		return enumerated_lines, local_logics, global_logics
	else:
		# Proceed to next line after '\n', '{' and '}'
		print_debug("{0} debug: End of line recursion.".format(
			ntabs(logic_level)))
		enumerated_lines, siblings, global_logics = _generate_keyword_tree(
			enumerated_lines, local_logics, global_logics, logic_level)
		return enumerated_lines, siblings, global_logics


def generate_logic_tree(act_branch):
	logic_tree = _generate_logic_tree(None, None, act_branch)
	return logic_tree


def _generate_logic_tree(keywords_owner, type_owner, keyword_branch):
	my_keywords = keyword_branch.keywords
	my_children = keyword_branch.children
	my_logic = None
	my_title = my_keywords[0]
	my_value = None
	my_value_type = None
	# Get value based on keywords length
	if len(my_keywords) == 1:
		pass
	elif len(my_keywords) == 2:
		my_value = my_keywords[1]
	else:
		print("Warning: Unexpected number of keywords in {0}.".format(
			my_keywords))
	my_type = "Unk"
	# Decide type by owner and then name
	if keywords_owner:
		if type_owner in ('Condition', 'Track',):
			my_type = "Param"
		elif keywords_owner.keywords[0] in ("ConditionGroup",):
			my_type = "Condition"
		elif keywords_owner.keywords[0] == "Tracks":
			my_type = "Track"
		elif type_owner in ('Param') and len(keyword_branch.children):
			my_type = "Condition"
	if my_type == "Unk":
		if my_title == "Bank":
			my_type = "Bank"
		elif my_title == "Node":
			my_type = "Node"
		elif my_title in ("ConditionGroup", "Tracks"):
			my_type = "Node"
		elif my_title == "FileReference":
			my_type = "FileReference"
		elif my_value:
			my_type = "Param"
		elif len(keyword_branch.children):
			my_type = "Param"
			my_value_type = "cg"
		else:
			print(
				"Warning: Unable to identify type of '{0}'.".format(my_title))
			my_type = "Node"
	# Create LogicNode
	my_logic = LogicNode(my_title, my_type, my_value,
						 my_value_type, [], [], [], [])
	new_children = []
	for c1 in my_children:
		child_logic = _generate_logic_tree(keyword_branch, my_type, c1)
		# Move logic under "ConditionGroup" and "Tracks" to a single main node
		if child_logic.title in ('ConditionGroup') and child_logic.type in ('Node',):
			for c2 in child_logic.children:
				if c2.type in ('Condition'):
					my_logic.conditions.append(c2)
		elif child_logic.title in ('Tracks') and child_logic.type in ('Node',):
			for c2 in child_logic.children:
				if c2.type in ('Track'):
					my_logic.tracks.append(c2)
		elif child_logic.type in ('Param'):
			my_logic.params.append(child_logic)
		else:
			new_children.append(child_logic)
	# Set value_type
	if my_logic.value_type is None:
		my_logic.value_type = get_value_type(my_value)
		# jank
		if my_logic.value_type == "none" and len(new_children):
			my_logic.value_type = "cg"
	# Overwrite current children
	my_logic.children = new_children
	return my_logic


def get_logic_nodes(logic_tree):
	nodes = []
	nodes.append(logic_tree)
	for c in logic_tree.children:
		nodes = nodes + get_logic_nodes(c)
	return nodes


def gather_logic(logic_nodes):
	conditions = []
	tracks = []
	for n in logic_nodes:
		for c in n.conditions:
			conditions.append(c)
		for t in n.tracks:
			tracks.append(t)
	return conditions, tracks


def get_param_id_from_param_title(param):
	# Get param id from [00000] or param00000, if possible
	id_string = ''
	if param.title.startswith('[') or param.title.startswith('param'):
		for c in param.title:
			if c.isdigit():
				id_string += c
	if len(id_string):
		return int(id_string)
	else:
		return None


def match_param_database(logic_title, logic_param, db):
	# Match param with DbTracks' and DbConditions' params
	param_id = get_param_id_from_param_title(logic_param)
	param_match = None
	for dblogic in db:
		if dblogic.title == logic_title:
			# DbCondition match
			for p in dblogic.params:
				if param_id is None:
					# Unable to get param id from param title
					# Match by title instead
					if p.title == logic_param.title:
						# Param match
						param_match = p
						break
				else:
					# Param id acquired from title
					# Match by raw ID
					if int(p.id) == int(param_id):
						# Param match
						param_match = p
						break
	return param_match


def get_sleeper_strings():
	for sl in offset_manager.sleeping_tracks + offset_manager.sleeping_conditions:
		# get strings from optimization, if possible
		if bool_enable_param_optimization:
			match = False
			for lo in logic_optimizations:
				if sl.logic == lo.sleeping_logic.logic:
					if lo.optimization:
						match = True
						my_params = lo.optimization.unique_params
						break
		if not bool_enable_param_optimization or not match:
			my_params = sl.logic.params
		# gather strings
		for p in my_params:
			if p.value_type == "string":
				my_string = strip_string(p.value)
				if len(my_string):
					ss = SleepingString(my_string, [p], [], [], [])
					offset_manager.add_sleeping_string(ss)


def write_string_variables(file):
	for ss in offset_manager.sleeping_strings:
		ss.string_slots.append(file.tell())
		# pad empty string offset
		format_write(file, 0, "I")
		# write number of times this string is used as parameter
		number_of_uses = len(ss.string_users)
		format_write(file, number_of_uses, "H")
		# pad (x) integers
		for i in range(0, number_of_uses):
			ss.param_slots.append(file.tell())
			format_write(file, 0, "I")


def get_sleeper_groups():
	### NOTE: DO NOT FORGET ###
	### The reason this is returning less groups than expected
	### is because groups are gathered from sleeping_tracks and sleeping_conditions
	### and these are getting merged down when run through get_early_sleepers()
	for sl in offset_manager.sleeping_tracks + offset_manager.sleeping_conditions:
		# get groups from optimizations, if possible
		if bool_enable_param_optimization:
			match = False
			for lo in logic_optimizations:
				if sl.logic == lo.sleeping_logic.logic:
					if lo.optimization:
						match = True
						my_params = lo.optimization.unique_params
						break
		if not bool_enable_param_optimization or not match:
			my_params = sl.logic.params
		# gather cg as usual
		for p in my_params:
			if p.value_type == "cg" and len(p.children):
				sg = SleepingGroup(p, [p], [], [], [], [], [])
				offset_manager.add_sleeping_group(sg)
				# offset_manager.sleeping_groups.append(sg)


def write_group_variables(file):
	for sg in offset_manager.sleeping_groups:
		sg.group_slots.append(file.tell())
		# pad empty condition group offset
		format_write(file, 0, "I")
		# write number of times this group is used as a parameter
		number_of_uses = len(sg.cg_users)
		format_write(file, number_of_uses, "H")
		# pad (x) integers
		for i in range(0, number_of_uses):
			sg.param_slots.append(file.tell())
			format_write(file, 0, "I")


def get_early_sleepers(logic_tree):
	my_logic = logic_tree
	my_type = my_logic.type
	# set up sleeping reference strings
	if my_type in ('FileReference'):
		file_name = None
		file_path = None
		for p in my_logic.params:
			if p.title == 'fileName':
				file_name = p.value[1:-1]
			if p.title == 'path':
				file_path = p.value[1:-1]
		ss = SleepingString(file_name, [], [], [], [])
		offset_manager.add_sleeping_reference_string(ss)
		ss = SleepingString(file_path, [], [], [], [])
		offset_manager.add_sleeping_reference_string(ss)
	# set up sleeping condition
	elif my_type in ('Condition'):
		sl = SleepingLogic(my_logic, [], None)
		offset_manager.add_sleeping_condition(sl)
		# offset_manager.sleeping_conditions.append(sl)
	# set up sleeping tracks
	elif my_type in ('Track'):
		sl = SleepingLogic(my_logic, [], None)
		offset_manager.add_sleeping_track(sl)
		# offset_manager.sleeping_tracks.append(sl)
	# debug
	'''
	for c in my_logic.params:
		if c.type in ('Param') and c.children:
			print(my_type, c.value_type)
	'''
	# call recursion
	for c in my_logic.conditions + my_logic.tracks + my_logic.params + my_logic.children:
		get_early_sleepers(c)


def write_cat_tree(file, logic_tree):
	my_logic = logic_tree
	my_type = my_logic.type
	number_of_children = len(my_logic.children)
	# print character based on type
	if my_type in ('Bank'):
		counter_manager.counterA += 1
		format_write(file, 'b', "c")
	elif my_type in ('Node'):
		if number_of_children:
			counter_manager.counterB += 1
			format_write(file, 'n', "c")
		else:
			counter_manager.counterB += 1
			counter_manager.counterD += 1
			format_write(file, 'l', "c")
	elif my_type in ('FileReference'):
		file_name = None
		file_path = None
		counter_manager.counterC += 1
		for p in my_logic.params:
			if p.title == 'includeFile':
				if p.value.upper() == "TRUE":
					format_write(file, 'i', "c")
				else:
					format_write(file, 'r', "c")
			if p.title == 'fileName':
				file_name = p.value[1:-1]
			if p.title == 'path':
				file_path = p.value[1:-1]
		# Set up sleeping reference string
		my_offset = file.tell()
		ss = SleepingString(file_name, [], [my_offset], [], [])
		offset_manager.add_sleeping_reference_string(ss)
		ss = SleepingString(file_path, [], [my_offset+4], [], [])
		offset_manager.add_sleeping_reference_string(ss)
		# Write padding
		format_write(file, 0, "I")
		format_write(file, 0, "I")
	# print hash
	if my_type in ('Bank', 'Node'):
		if my_logic.value_type == "bytes":
			my_hash = bytearray.fromhex(my_logic.value[2:].upper())
			file.write(my_hash)
		else:
			hashed_title = hash_cat_title(my_logic.value)
			file.write(hashed_title)
	# optimization jank -- since tracks and conditions get merged when converted to sleeping tracks
	#	my_logic.tracks and my_logic.conditions aren't accurate anymore
	# NOTE: conditions must be allowed to be repeated here
	#	for example, multiple identical NOT nodes can be used in a bank's condition group
	#	and that must be allowed
	# NOTE: can't compare old tracks with new optimized tracks because they are different when optimized
	my_conditions = []
	for c in my_logic.conditions:
		if c in [c.logic for c in offset_manager.sleeping_conditions]:
			my_conditions.append(c)
		else:
			print("Warning: Unable to match tree condition {0} with sleeping conditions.".format(c.title))
	my_tracks = []
	for t in my_logic.tracks:
		if t in [t.logic for t in offset_manager.sleeping_tracks]:
			my_tracks.append(t)
		else:
			print("Warning: Unable to match tree track {0} with sleeping tracks.".format(t.title))
	# print conditions
	if my_type in ('Bank', 'Node'):
		format_write(file, len(my_conditions), "B")
		for c in my_conditions:
			# Update existing sleeping condition
			my_offset = file.tell()
			for sc in offset_manager.sleeping_conditions:
				if sc.logic == c:
					sc.logic_slots.append(my_offset)
					break
			# Write padding
			format_write(file, 0, "I")
	# print tracks
	if my_type in ('Node'):
		format_write(file, len(my_tracks), "B")
		for t in my_tracks:
			# Update existing sleeping track
			my_offset = file.tell()
			for st in offset_manager.sleeping_tracks:
				if st.logic == t:
					st.logic_slots.append(my_offset)
					break
			# Write padding
			format_write(file, 0, "I")
	# print number of children
	if my_type in ('Bank', 'Node'):
		format_write(file, number_of_children, "H")
	# call recursion
	for c in my_logic.children:
		write_cat_tree(file, c)


def write_param_value_by_param_type(file, sleeping_logic, param, db_param_type):
	value = param.value
	value_type = param.value_type
	if value_type == "bytes":
		value = value[2:]
		try:
			value = bytearray.fromhex(value)
		except:
			print("Error: Mismatched param type '{0}' on value '{1}', expected bytes. Writing zero. (Try generating templates)".format(
				param.value_type, param.value))
			value = bytearray.fromhex("00000000")
		file.write(value)
	elif value_type == "int":
		format_write(file, int(value), "i")
	elif value_type == "bool":
		string = str(value).upper()
		if '1' in string or "TRUE" in string:
			format_write(file, 1, "B")
		else:
			format_write(file, 0, "B")
	elif value_type == "float":
		format_write(file, float(value), "f")
	elif value_type == "string":
		# Try to match with sleeping strings first
		match = False
		value = strip_string(value)
		for ss in offset_manager.sleeping_strings:
			if ss.string == value:
				if len(ss.param_slots) > len(ss.param_offsets):
					match = True
					ss.param_offsets.append(file.tell())
					break
		if match:
			format_write(file, 0, "I")
		else:
			hash = hash_cat_value(value)
			file.write(hash)
	elif value_type == "hashed_string":
		# Remove 'h' and quotes from string
		if value.startswith('h\"'):
			value = value[2:-1]
		hash = hash_cat_value(value)
		file.write(hash)
	elif value_type == "cg":
		# Ignore CG if no children (should have conditions -- verify later)
		if not len(param.children):
			format_write(file, 0, "I")
		else:
			# Match with sleeping groups
			match = False
			for sg in offset_manager.sleeping_groups:
				if sg.cg_param == param:
					if len(sg.param_slots) > len(sg.param_offsets):
						match = True
						sg.param_offsets.append(file.tell())
						break
			if not match:
				print("Error: Param '{0}' type '{1}' from '{2}' could not be matched to variable condition group.".format(
					param.title, param.value_type, sleeping_logic.logic.title))
			format_write(file, 0, "I")
	else:
		print("Error: Unable to handle param type '{0}' on value '{1}', writing value zero.".format(
			param.value_type, param.value))
		format_write(file, 0, "I")


def optimize_track_params(logic_tree):
	def get_param_id(sleeping_logic, param):
		param_match_db = match_param_database(
			sleeping_logic.logic.title, param, db_tracks)
		if param_match_db:
			return int(param_match_db.id)
		else:
			param_id = get_param_id_from_param_title(param)
			if param_id is not None:
				return param_id
			else:
				print("Error: Unable to get param id for param '{0}'.".format(
					sl.logic.title))

	@dataclass
	class ParamMatch:
		paramA: LogicNode
		paramB: LogicNode

	@dataclass
	class LogicMatch:
		logicA: SleepingLogic
		logicB: SleepingLogic
		param_matches: list[ParamMatch]
		unique_params: list[LogicNode]
	# Generate new list of optimized tracks
	# TO-DO:
	# 1	--	check rules of optimization in original files
	logic_optimizations = []
	start_time = time.time()
	number_of_verified_tracks = 0
	total_bytes_saved = 0
	for i, st1 in enumerate(offset_manager.sleeping_tracks):
		best_match = None
		for j, st2 in enumerate(offset_manager.sleeping_tracks):
			if i >= j:
				# optimization can't go back, only forward
				continue
			else:
				# early skip if optimization isn't worth it
				if best_match is not None and len(best_match.param_matches) > len(st2.logic.params):
					continue
				# quick optimization -- skip mismatched hashes
				hash_match = st1.logic.title == st2.logic.title
				if bool_quick_param_optimization and not hash_match:
					continue
				# NOTE: Must verify if optimization target has extra params IDs
				# that optimization source doesn't have
				# otherwise source receives GHOST PARAMS that weren't originally there
				# In the future, test idea of replacing bad ID values with 0
				p1_ids = [get_param_id(st1, p) for p in st1.logic.params]
				p2_ids = [get_param_id(st2, p) for p in st2.logic.params]
				if p1_ids != p2_ids:
					continue
				# Create list of param matches
				param_matches = []
				for p1 in st1.logic.params:
					if p1.value_type in ('cg'):
						# ignore cg params -- their value is 'None'
						# optimization only checks id & values not chilldren
						continue
					pid1 = get_param_id(st1, p1)
					for p2 in st2.logic.params:
						pid2 = get_param_id(st2, p2)
						if pid1 == pid2:
							if p1.value == p2.value:
								# param match has been found
								pm = ParamMatch(p1, p2)
								param_matches.append(pm)
				# done checking param matches with st2
				if len(param_matches):
					# if any param matches, store as optimization match
					if best_match is None or len(param_matches) > len(best_match.param_matches):
						lm = LogicMatch(st1, st2, param_matches, [])
						best_match = lm
		# done checking for optimization matches for st1
		# update total verified tracks
		number_of_verified_tracks += 1
		if best_match:
			# get total bytes saved
			for pm in best_match.param_matches:
				if pm.paramA.value_type == "bool":
					total_bytes_saved += 1
				else:
					total_bytes_saved += 4
			# add unique params to logic match
			unique_params = []
			for p in st1.logic.params:
				if p not in [pm.paramA for pm in best_match.param_matches]:
					unique_params.append(p)
			best_match.unique_params = unique_params
			osl = LogicOptimization(st1, best_match)
			logic_optimizations.append(osl)
			print("->->-> Track {1}/{2}, optimized {0} params.".format(len(
				best_match.param_matches), number_of_verified_tracks, len(offset_manager.sleeping_tracks)))
		else:
			osl = LogicOptimization(st1, None)
			logic_optimizations.append(osl)
			print("->->-> Track {0}/{1}, no optimizable params.".format(
				number_of_verified_tracks, len(offset_manager.sleeping_tracks)))
	# End of optimization
	end_time = time.time()
	optimization_time = end_time - start_time
	print("->->-> Time spent optimizing track params: {0} seconds; Bytes saved: {1}.".format(
		round(optimization_time, 2), total_bytes_saved))
	return logic_optimizations


def write_param_data(file, logic_tree):
	# for sl in offset_manager.sleeping_conditions+offset_manager.sleeping_group_conditions:
	# removed sleeping group conditions temporarily, verify if still necessary
	for sl in offset_manager.sleeping_conditions:
		# Setup
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Write pointers
		for lpo in sl.logic_slots:
			file.seek(lpo, 0)
			format_write(file, safe_pos - p_data, "I")
		file.seek(safe_pos)
		# Write condition hash
		hashed_title = hash_cat_value(sl.logic.title)
		file.write(hashed_title)
		# Write params
		number_of_params = len(sl.logic.params)
		for logic_param in sl.logic.params:
			param_id = get_param_id_from_param_title(logic_param)
			param_match = match_param_database(
				sl.logic.title, logic_param, db_conditions)
			if param_match:
				write_param_value_by_param_type(file, sl, logic_param, param_match.type)
			else:
				write_param_value_by_param_type(file, sl, logic_param, None)
	for sl in offset_manager.sleeping_tracks:
		# Setup
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Get params from optimizations, if possible
		if bool_enable_param_optimization:
			match = False
			for lo in logic_optimizations:
				if sl.logic == lo.sleeping_logic.logic:
					if lo.optimization:
						match = True
						my_params = lo.optimization.unique_params
						break
		if not bool_enable_param_optimization or not match:
			my_params = sl.logic.params
		number_of_params = len(my_params)
		# Write pointers
		for lpo in sl.logic_slots:
			file.seek(lpo)
			format_write(file, safe_pos - p_data, "I")
		file.seek(safe_pos)
		# Pad optimization offset
		format_write(file, 0, "H")
		# Write track hash and flags		-> to-do: add track hash to optimization
		hashed_title = hash_cat_value(sl.logic.title)
		param_id = 0
		param_id |= 0x0004
		if number_of_params:
			param_id |= 0x0001
		format_write(file, param_id, "H")
		file.write(hashed_title)
		# Write params
		for i, logic_param in enumerate(my_params):
			param_id = get_param_id_from_param_title(logic_param)
			param_match = match_param_database(sl.logic.title, logic_param, db_tracks)
			# Write param flags
			if param_match:
				param_id = int(param_match.id)
				param_id <<= 3
				if (param_match.type != 'bool'):
					param_id |= 0x0004
			else:
				print_debug("Warning: Unable to match param {0} in param database.".format(logic_param.title))
				param_id <<= 3
				if logic_param.value_type not in ("bool", ):
					param_id |= 0x0004
			if not param_id:
				print("Bug: Unable to find ID for param, file will break.")
				param_id = 0
			if (i < number_of_params-1):
				param_id |= 0x0001
			# Write param id
			format_write(file, param_id, "H")
			# Write param value
			if param_match:
				write_param_value_by_param_type(file, sl, logic_param, param_match.type)
			else:
				write_param_value_by_param_type(file, sl, logic_param, None)
	# fix sleeping tracks optimization offsets
	if bool_enable_param_optimization:
		safe_pos = file.tell()
		for sl in offset_manager.sleeping_tracks:
			for lm in logic_optimizations:
				if sl == lm.sleeping_logic:
					if lm.optimization:
						file.seek(lm.optimization.logicA.logic_offset)
						distance = lm.optimization.logicB.logic_offset - lm.optimization.logicA.logic_offset
						if distance > 32767:
							print("Error: Optimization distance is bigger than 32767, this will break the file.")
						format_write(file, distance, "H")
		file.seek(safe_pos)
	# end -> make sure to either save a new safe_pos
	# or remove file.seek() otherwise last track will be corrupted
	safe_pos = file.tell()
	file.seek(safe_pos)


def _write_strings(file, sleeping_list):
	for s in sleeping_list:
		safe_pos = file.tell()
		my_offset = safe_pos - p_strings
		# (Multiple offsets required because of 'FileReference')
		for slot in s.string_slots:
			file.seek(slot, 0)
			format_write(file, my_offset, "I")
		# Write param_offsets on param_slot_offsets
		len1 = len(s.param_slots)
		len2 = len(s.param_offsets)
		if len1 != len2:
			print("Error: STRING '{2}' has mismatching number of param_slots ({0}) and param_offsets ({1}).".format(
				len1, len2, s.string))
		else:
			for i, po in enumerate(s.param_offsets):
				param_safe_pos = file.tell()
				var_pos = s.param_slots[i]
				file.seek(var_pos)
				format_write(file, po - p_data, "I")
				file.seek(param_safe_pos)
		# Write string
		file.seek(safe_pos, 0)
		bstring = bytes(s.string, 'utf-8') + b'\x00'
		file.write(bstring)


def write_strings(file):
	_write_strings(file, offset_manager.sleeping_strings)


def write_reference_strings(file):
	_write_strings(file, offset_manager.sleeping_reference_strings)


def write_groups(file):
	for g in offset_manager.sleeping_groups:
		safe_pos = file.tell()
		my_offset = safe_pos - p_groups
		# Write my_offset on group_slot_offsets
		for offset in g.group_slots:
			file.seek(offset)
			format_write(file, my_offset, "I")
		# Write number of conditions
		file.seek(safe_pos, 0)
		format_write(file, len(g.cg_param.children), "B")
		# Write padding for each condition offset and add extra sleeping conditions
		# since these conditions are not listed within the node tree
		for c in g.cg_param.children:
			condition_pointer_offset = file.tell()
			g.condition_slots.append(condition_pointer_offset)
			format_write(file, 0, "I")
			# sl = SleepingLogic(c, [condition_pointer_offset], None)
			# offset_manager.add_sleeping_group_condition(sl)
			# offset_manager.add_sleeping_condition(sl)
			# Update existing sleeping conditions
			for sc in offset_manager.sleeping_conditions:
				if sc.logic == c:
					sc.logic_slots.append(condition_pointer_offset)
					break


def fix_group_offsets(file):
	safe_pos = file.tell()
	debug_counter = 0

	for i, group in enumerate(offset_manager.sleeping_groups):
		# Run through all sleeping conditions
		# Check which ones are used in condition groups
		# Append their offset to their corresponding groups
		for sgc in group.cg_param.children:
			# sgc is a condition of this 'cg'
			# for sl in offset_manager.sleeping_group_conditions:
			for sl in offset_manager.sleeping_conditions:
				if sgc == sl.logic:
					group.condition_offsets.append(sl.logic_offset)
					break
		# Write condition offsets into condition pointer offsets
		len1 = len(group.condition_slots)
		len2 = len(group.condition_offsets)
		if len1 != len2:
			print("Error: GROUP {0} has mismatching number of condition_slots ({1}) and condition_offsets ({2}).".format(
				i, len1, len2))
		else:
			for i, po in enumerate(group.condition_offsets):
				param_safe_pos = file.tell()
				var_pos = group.condition_slots[i]
				file.seek(var_pos)
				format_write(file, po - p_data, "I")
				file.seek(param_safe_pos)
		# Write param offsets into param pointer offsets
		len1 = len(group.param_slots)
		len2 = len(group.param_offsets)
		if len1 != len2:
			print("Error: GROUP {0} has mismatching number of param_slots ({1}) and param_offsets ({2}).".format(
				i, len1, len2))
		else:
			for i, po in enumerate(group.param_offsets):
				param_safe_pos = file.tell()
				var_pos = group.param_slots[i]
				file.seek(var_pos)
				format_write(file, po - p_data, "I")
				file.seek(param_safe_pos)
	file.seek(safe_pos, 0)


## DB LOGIC ##
def read_db_logics(file):
	db_logics = []
	lines = file.readlines()
	last_logic = None
	for l in lines:
		my_line = l.split()
		if len(my_line) == 0 or l[0] == '#':
			continue
		if l[0] != "\t":
			if last_logic is not None:
				db_logics.append(last_logic)
			logic = DbLogic(my_line[0], [])
			last_logic = logic
		else:
			p = DbParam(my_line[0], my_line[1], my_line[2])
			last_logic.params.append(p)
	if last_logic is not None:
		db_logics.append(last_logic)
	return db_logics


## SETUP ##
# path = str(Path(__file__).parent) + os.sep
reference_strings = []
offset_manager = OffsetManager([], [], [], [], [], [])
counter_manager = CounterManager()

# WARNING: track db and condition db must be kept separate
# because there are nodes that share the same name (both track/condition)

## READ TRACK DB ##
fn_track_templates = "TEMPLATES"+os.sep+"TEMPLATES_TRACKS.txt"
db_tracks = []
if os.path.exists(fn_track_templates):
	file_dbt = open(fn_track_templates)
	db_tracks = read_db_logics(file_dbt)
	file_dbt.close()
else:
	print("Warning: No '{0}' found.".format(fn_track_templates))

## READ CONDITION DB ##
fn_condition_templates = "TEMPLATES"+os.sep+"TEMPLATES_CONDITIONS.txt"
db_conditions = []
if os.path.exists(fn_condition_templates):
	file_dtc = open(fn_condition_templates)
	db_conditions = read_db_logics(file_dtc)
	file_dtc.close()
else:
	print("Warning: No '{0}' found.".format(fn_condition_templates))


# Get MACT files from sys.argv
my_mact_files = []
sys_argv = sys.argv[1:]
for i, arg in enumerate(sys_argv):
	if sys_argv[i].upper() == "--PO":
		bool_enable_param_optimization = True
	if sys_argv[i].endswith(".mact"):
		my_mact_files.append(sys_argv[i])
if not len(my_mact_files):
	print("Error: No MACT files found.")
	quit()

for fmact in my_mact_files:
	## ACT / MACT INPUT ##
	print("<< {0} >>".format(fmact))
	fn_input = fmact
	f_input = open(fn_input, "r")
	my_lines = f_input.readlines()
	f_input.close()

	## PROCESSING ##
	print("-> Generating keyword tree.")
	keyword_tree = generate_keyword_tree(my_lines)
	print("-> Generating logic tree.")
	logic_tree = generate_logic_tree(keyword_tree)
	if bool_print_tree:
		logic_tree.print_tree()
	logic_nodes = get_logic_nodes(logic_tree)

	## SET SLEEPER LOGIC ##
	get_early_sleepers(logic_tree)

	## WIP OPTIMIZE TRACK PARAMS ##
	print("->-> Optimizing track parameter data.")
	if not bool_enable_param_optimization:
		print("->->-> WARNING: Track param optimization is disabled, this will result in bigger file sizes.")
	else:
		if not bool_quick_param_optimization:
			print(
				"->->-> WARNING: Slow track param optimization selected, this might take several minutes.")
		logic_optimizations = optimize_track_params(logic_tree)

	# Gather before writing
	get_sleeper_strings()
	# NOTE: THEORY: optimization currently decreases number of groups
	#	because in groups with identical nodes but different params
	#	params can get optimized into looking identical,
	#	which makes it so the groups get merged into one.
	# NOTE: However, if params can get optimized into looking identical,
	#	then they had no unique data to begin with.
	#	So the groups are identical.
	get_sleeper_groups()

	## OUTPUT ##
	print("-> Writing CAT file.")
	fn_cat = fn_input.rsplit(os.sep, 1)[-1].split('.')[0] + ".cat"
	f_cat = open(fn_cat, "wb")

	## HEADER ##
	print("->-> Writing header data.")
	format_write(f_cat, 0, "I")  # file_length
	format_write(f_cat, 0, "I")  # p_data
	format_write(f_cat, 0, "I")  # p_strings
	format_write(f_cat, 0, "I")  # p_groups
	format_write(f_cat, 0, "I")  # counterA
	format_write(f_cat, 0, "I")  # counterB
	format_write(f_cat, 0, "I")  # counterC
	format_write(f_cat, 0, "I")  # counterD

	## VARIABLES ##
	format_write(f_cat, 0, "I")  # number_of_strings
	write_string_variables(f_cat)
	p_var_groups = f_cat.tell()
	format_write(f_cat, 0, "I")  # number_of_condition_groups
	write_group_variables(f_cat)

	## CAT TREE ##
	print("->-> Writing CAT tree.")
	write_cat_tree(f_cat, logic_tree)

	## CONDITION GROUPS ##
	p_groups = f_cat.tell()
	write_groups(f_cat)

	## PARAMS DATA ##
	print("->-> Writing parameter data.")
	p_data = f_cat.tell()
	write_param_data(f_cat, logic_tree)

	## STRINGS ##
	print("->-> Writing string data.")
	p_strings = f_cat.tell()
	write_strings(f_cat)
	write_reference_strings(f_cat)

	## FIX HEADER & OFFSETS ##
	print("->-> Fixing offsets.")
	file_length = f_cat.tell()
	fix_group_offsets(f_cat)  # fix var param group offsets
	# return to start to fix header
	f_cat.seek(0, 0)
	format_write(f_cat, file_length, "I")  # file_length
	format_write(f_cat, p_data, "I")  # p_data
	format_write(f_cat, p_strings, "I")  # p_strings
	format_write(f_cat, p_groups, "I")  # p_groups
	format_write(f_cat, counter_manager.counterA - 1, "I")  # counterA
	format_write(f_cat, counter_manager.counterB, "I")  # counterB
	format_write(f_cat, counter_manager.counterC, "I")  # counterC
	format_write(f_cat, counter_manager.counterD, "I")  # counterD
	format_write(f_cat, len(offset_manager.sleeping_strings),
				 "I")  # number_of_strings_vars
	f_cat.seek(p_var_groups, 0)
	format_write(f_cat, len(offset_manager.sleeping_groups),
				 "I")  # number_of_groups_vars
	f_cat.seek(file_length, 0)

	## END ##
	print("->-> Writing padding.")
	pad = file_length % 1024
	pad = 1024 - pad
	f_cat.write(pad*b'\00')
	f_cat.close()

	if bool_print_debug and False:
		fn_debug = fn_input.split('.')[0] + "_debug.txt"
		f_debug = open(fn_debug, "w")
		keyword_tree.write_tree(f_debug)
		f_debug.close()
	
	## DEBUG INFO ##
	debug_mismatched_strings = 0
	debug_mismatched_groups = 0
	debug_unused_strings = 0
	debug_unused_groups = 0
	debug_unused_conditions = 0
	debug_unused_tracks = 0
	print("->-> Debug Information.")
	for i, s in enumerate(offset_manager.sleeping_strings):
		if len(s.param_slots) != len(s.param_offsets):
			debug_mismatched_strings += 1
		if len(s.param_offsets) == 0:
			debug_unused_strings += 1
	for i, s in enumerate(offset_manager.sleeping_groups):
		if len(s.param_slots) != len(s.param_offsets):
			debug_mismatched_groups += 1
			# print("Warning: GROUP {0} has mismatched param_slots ({1}) and param_offsets ({2})!".format(i, len(sl.param_slots), len(sl.param_offsets)))
		if len(s.param_offsets) == 0:
			debug_unused_groups += 1
			# print("Warning: GROUP {0} has no param_offsets ({2})!".format(i, len(sl.param_slots), len(sl.param_offsets)))
	for i, s in enumerate(offset_manager.sleeping_conditions):
		if len(s.logic_slots) == 0:
			debug_unused_conditions += 1
			# print("Warning: CONDITION {0} wasn't used inside CAT TREE!".format(s.logic.title))
		if s.logic_offset == None or s.logic_offset == 0:
			debug_unused_conditions += 1
			# print("Warning: CONDITION {0} is unused!".format(s.logic.title))
	for i, s in enumerate(offset_manager.sleeping_tracks):
		if len(s.logic_slots) == 0:
			debug_unused_tracks += 1
		if s.logic_offset == None or s.logic_offset == 0:
			debug_unused_tracks += 1
	print("Info: {0} total strings, {1} mismatched strings and {2} unused strings.".format(len(offset_manager.sleeping_strings), debug_mismatched_strings, debug_unused_strings))
	print("Info: {0} total groups, {1} mismatched groups and {2} unused groups.".format(len(offset_manager.sleeping_groups), debug_mismatched_groups, debug_unused_groups))
	print("Info: {0} total conditions, {1} unused conditions.".format(len(offset_manager.sleeping_conditions), debug_unused_conditions))
	print("Info: {0} total tracks, {1} unused tracks.".format(len(offset_manager.sleeping_tracks), debug_unused_tracks))
	# print("Info: {0} merged strings, {1} merged groups, {2} merged logic.".format(offset_manager.debug_merged_strings, offset_manager.debug_merged_groups, offset_manager.debug_merged_logic))


# End #
print("-> Done.")
quit()
