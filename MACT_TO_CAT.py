# MARCDRED'S MACT_TO_CAT.py V3.3.1 #
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

# GOALS:
# --	Slightly decrease param type dependency to template files.
# --	Add optimization to TRACKS so that files are smaller and you can have more of them without breaking the game.
# --	Improve error handling/debugging.

## SETTINGS ##
bool_print_debug = False
bool_print_tree = False
bool_little_endian = True
bool_enable_optimization = False
# for Nemesis.cat quick optimization takes 22 sec, slow optimization takes 2 minutes (rarely worth it)
bool_quick_optimization = True

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

	def _add_sleeping_string(self, new_ss, sleeper_list):
		repeated = False
		for old_ss in sleeper_list:
			if old_ss.string == new_ss.string:
				repeated = True
				for user in new_ss.string_users:
					old_ss.string_users.append(user)
				for offset in new_ss.string_slots:
					old_ss.string_slots.append(offset)
		if not repeated:
			sleeper_list.append(new_ss)

	def add_sleeping_string(self, new_ss):
		self._add_sleeping_string(new_ss, self.sleeping_strings)

	def add_sleeping_reference_string(self, new_ss):
		self._add_sleeping_string(new_ss, self.sleeping_reference_strings)

	def _add_sleeping_group(self, new_sg, sleeper_list):
		repeated = False
		for old_sg in sleeper_list:
			if old_sg.cg_param == new_sg.cg_param:
				repeated = True
				for user in new_sg.cg_users:
					old_sg.cg_users.append(user)
				for offset in new_sg.group_slots:
					old_sg.group_slots.append(offset)
		if not repeated:
			sleeper_list.append(new_sg)

	def add_sleeping_group(self, new_sg):
		self._add_sleeping_group(new_sg, self.sleeping_groups)

	def _add_sleeping_logic(self, new_sl, sleeper_list):
		repeated = False
		for old_sl in sleeper_list:
			if old_sl.logic == new_sl.logic:
				repeated = True
				for offset in new_sl.logic_slot_offsets:
					old_sl.logic_slot_offsets.append(offset)
		if not repeated:
			sleeper_list.append(new_sl)

	def add_sleeping_condition(self, new_sl):
		self._add_sleeping_logic(new_sl, self.sleeping_conditions)

	def add_sleeping_group_condition(self, new_sg):
		self._add_sleeping_logic(new_sg, self.sleeping_group_conditions)

	def add_sleeping_track(self, new_sl):
		self._add_sleeping_logic(new_sl, self.sleeping_tracks)


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
	logic: ActLogic
	# LOGIC SLOT <- Receives logic offsets
	logic_slot_offsets: list[int]
	logic_offset: int


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
	# Create ActLogic
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


def gather_sleeper_strings():
	for sl in offset_manager.sleeping_tracks + offset_manager.sleeping_conditions:
		for p in sl.logic.params:
			if p.value_type == "string":
				my_value = strip_string(p.value)
				# Check if any remaining string before continuing
				if len(my_value):
					ss = SleepingString(my_value, [sl.logic], [], [], [])
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


def gather_sleeper_groups():
	debug_counter = 0
	for sl in offset_manager.sleeping_tracks + offset_manager.sleeping_conditions:
		for p in sl.logic.params:
			if p.value_type == "cg" and len(p.children):
				# print(sl.logic.title)
				sg = SleepingGroup(p, [sl.logic], [], [], [], [], [])
				offset_manager.add_sleeping_group(sg)
				debug_counter += 1


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


def set_early_sleepers(logic_tree):
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
	if my_type in ('Condition'):
		sl = SleepingLogic(my_logic, [], None)
		offset_manager.add_sleeping_condition(sl)
	# set up sleeping tracks
	if my_type in ('Track'):
		sl = SleepingLogic(my_logic, [], None)
		offset_manager.add_sleeping_track(sl)
	# call recursion
	for c in my_logic.conditions + my_logic.tracks + my_logic.params + my_logic.children:
		set_early_sleepers(c)


def write_cat_tree(file, logic_tree):
	my_logic = logic_tree
	my_type = my_logic.type
	number_of_children = len(my_logic.children)
	number_of_conditions = len(my_logic.conditions)
	number_of_tracks = len(my_logic.tracks)
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
	# print conditions
	if my_type in ('Bank', 'Node'):
		format_write(file, number_of_conditions, "B")
		for c in my_logic.conditions:
			# Set up sleeping condition
			my_offset = file.tell()
			sl = SleepingLogic(c, [my_offset], None)
			offset_manager.add_sleeping_condition(sl)
			# Write padding
			format_write(file, 0, "I")
	# print tracks
	if my_type in ('Node'):
		format_write(file, number_of_tracks, "B")
		for t in my_logic.tracks:
			# update sleeping track
			my_offset = file.tell()
			sl = SleepingLogic(t, [my_offset], None)
			offset_manager.add_sleeping_track(sl)
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


def optimize_param_data(logic_tree):
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
	class OptimizationMatch:
		logicA: SleepingLogic
		logicB: SleepingLogic
		param_matches: list[ParamMatch]
	# Generate new list of optimized tracks
	# TO-DO:
	# 1	--	check rules of optimization in original files
	optimized_sleeping_tracks = []
	start_time = time.time()
	number_of_verified_tracks = 0
	total_bytes_saved = 0
	for i, st1 in enumerate(offset_manager.sleeping_tracks):
		best_match = None
		for j, st2 in enumerate(offset_manager.sleeping_tracks):
			if i >= j:
				# optimization can't go back afaik, only forward
				continue
			else:
				# early skip if optimization check isn't worth it
				if best_match is not None and len(best_match.param_matches) > len(st2.logic.params):
					continue
				# quick optimization -- skip mismatched hashes
				hash_match = st1.logic.title == st2.logic.title
				if bool_quick_optimization and not hash_match:
					continue
				param_matches = []
				for p1 in st1.logic.params:
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
						om = OptimizationMatch(st1, st2, param_matches)
						best_match = om
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
			# store best match
			optimized_sleeping_tracks.append(best_match)
			print("->->-> Track {1}/{2}, optimized {0} params.".format(len(
				best_match.param_matches), number_of_verified_tracks, len(offset_manager.sleeping_tracks)))
		else:
			print("->->-> Track {0}/{1}, no optimizable params.".format(
				number_of_verified_tracks, len(offset_manager.sleeping_tracks)))
	# End of optimization
	end_time = time.time()
	optimization_time = end_time - start_time
	print("->->-> Time spent optimizing tracks: {0} seconds; Bytes saved: {1}.".format(
		round(optimization_time, 2), total_bytes_saved))
	return optimized_sleeping_tracks


def write_param_data(file, logic_tree, optimized_matches):
	for sl in offset_manager.sleeping_conditions+offset_manager.sleeping_group_conditions:
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Write pointers
		for lpo in sl.logic_slot_offsets:
			file.seek(lpo, 0)
			format_write(f_cat, safe_pos - p_data, "I")
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
				# Write param value using database match's type
				write_param_value_by_param_type(
					file, sl, logic_param, param_match.type)
			else:
				# Write param value using logic param's type
				print_debug(
					"Warning: No matching param ID: {0} in param database.".format(param_id))
				write_param_value_by_param_type(
					file, sl, logic_param, logic_param.value_type)
	for sl in offset_manager.sleeping_tracks:
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Write pointers
		for lpo in sl.logic_slot_offsets:
			file.seek(lpo, 0)
			format_write(f_cat, safe_pos - p_data, "I")
		file.seek(safe_pos)
		# Pad optimization offset
		format_write(file, 0, "H")
		# Write track hash
		# TO-DO:
		# 1	--	add track hash to optimization
		hashed_title = hash_cat_value(sl.logic.title)
		param_id = 0
		param_id |= 0x0004
		if len(sl.logic.params):
			param_id |= 0x0001
		format_write(file, param_id, "H")
		file.write(hashed_title)
		# Check for optimized params
		my_params = []
		for om in optimized_matches:
			if om.logicA == sl:
				for p in sl.logic.params:
					if p not in [pm.paramA for pm in om.param_matches]:
						my_params.append(p)
		if not len(my_params):
			# No param optimization
			my_params = sl.logic.params
		# Write params
		number_of_params = len(my_params)
		for i, logic_param in enumerate(my_params):
			param_id = get_param_id_from_param_title(logic_param)
			param_match = match_param_database(
				sl.logic.title, logic_param, db_tracks)
			# Write param flags
			if param_match:
				param_id = int(param_match.id)
				param_id <<= 3
				if (param_match.type != 'bool'):
					param_id |= 0x0004
			else:
				print_debug(
					"Warning: Unable to match param {0} in param database.".format(logic_param.title))
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
				# Write param value using database match's type
				write_param_value_by_param_type(
					file, sl, logic_param, param_match.type)
			else:
				# Write param value using logic param's type
				print_debug(
					"Warning: No matching param ID: {0} in param database.".format(param_id))
				write_param_value_by_param_type(
					file, sl, logic_param, logic_param.value_type)
	# fix sleeping tracks optimization offsets
	safe_pos = file.tell()
	for sl in offset_manager.sleeping_tracks:
		for om in optimized_matches:
			if om.logicB == sl:
				file.seek(om.logicA.logic_offset)
				format_write(file, om.logicB.logic_offset -
							 om.logicA.logic_offset, "H")
	# end
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
			sl = SleepingLogic(c, [condition_pointer_offset], None)
			offset_manager.add_sleeping_group_condition(sl)


def fix_group_offsets(file):
	safe_pos = file.tell()
	debug_counter = 0

	for i, group in enumerate(offset_manager.sleeping_groups):
		# Run through all sleeping conditions
		# Check which ones are used in condition groups
		# Append their offset to their corresponding groups
		for sgc in group.cg_param.children:
			# sgc is a condition of this group node
			for sl in offset_manager.sleeping_group_conditions:
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
	set_early_sleepers(logic_tree)
	gather_sleeper_strings()
	gather_sleeper_groups()

	## WIP OPTIMIZE TRACK PARAMS ##
	optimized_matches = []
	print("->-> Optimizing track parameter data.")
	if not bool_enable_optimization:
		print("->->-> WARNING: Optimization is disabled, this will result in bigger file sizes.")
	else:
		if not bool_quick_optimization:
			print(
				"->->-> WARNING: Slow optimization selected, this might take several minutes.")
		optimized_matches = optimize_param_data(logic_tree)

	## OUTPUT ##
	print("-> Writing CAT file.")
	fn_cat = fn_input.split('.')[0] + ".cat"
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
	write_param_data(f_cat, logic_tree, optimized_matches)

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

	# CODE DEBUG
	for g in offset_manager.sleeping_groups:
		print(g.param_slots, g.param_offsets)


# End #
print("Done.")
quit()
