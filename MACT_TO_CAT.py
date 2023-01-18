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


## SETTINGS ##
bool_print_debug = False
bool_print_tree = False
bool_little_endian = True


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
class LogicStringVariable:
	offset: int
	string: str
	source_logics: list[ActLogic]


@dataclass
class LogicGroupVariable:
	offset: int
	source_logics: list[ActLogic]


@dataclass
class OffsetManager:
	sleeping_strings: list[SleepingString]
	sleeping_groups: list[SleepingGroup]
	sleeping_reference_strings: list[SleepingString]
	sleeping_conditions: list[SleepingLogic]
	sleeping_group_conditions: list[SleepingLogic]
	sleeping_tracks: list[SleepingLogic]

	def _add_sleeping_string(self, new_ss, string_list):
		repeated = False
		for ss in string_list:
			if ss.string == new_ss.string:
				repeated = True
				for so in new_ss.var_string_offsets:
					ss.var_string_offsets.append(so)
		if not repeated:
			string_list.append(new_ss)

	def add_sleeping_group(self, new_sg):
		self.sleeping_groups.append(new_sg)

	def add_sleeping_string(self, new_ss):
		self._add_sleeping_string(new_ss, self.sleeping_strings)

	def add_sleeping_reference_string(self, new_ss):
		self._add_sleeping_string(new_ss, self.sleeping_reference_strings)

	def _add_sleeping_logic(self, new_logic, logic_list):
		repeated = False
		for logic in logic_list:
			if logic.logic == new_logic:
				repeated = True
		if not repeated:
			logic_list.append(new_logic)

	def add_sleeping_condition(self, new_logic):
		self._add_sleeping_logic(new_logic, self.sleeping_conditions)
	
	def add_sleeping_group_condition(self, new_logic):
		self._add_sleeping_logic(new_logic, self.sleeping_group_conditions)

	def add_sleeping_track(self, new_logic):
		self._add_sleeping_logic(new_logic, self.sleeping_tracks)


@dataclass
class CounterManager:
	counterA: int = 0
	counterB: int = 0
	counterC: int = 0
	counterD: int = 0


@dataclass
class SleepingString:
	string: str
	# var_string_offsets has to be a list because of 'FileReference'
	# They sometimes reutilize the same string multiple times and we don't wanna
	# write it again for each use
	var_string_offsets: list[int]
	string_offsets: list[int]
	var_param_offsets: list[int]
	param_offsets: list[int]


@dataclass
class SleepingGroup:
	logic_node: LogicNode
	var_group_offset: int
	group_offset: int
	var_condition_offsets: list[int]
	condition_offsets: list[int]
	var_param_offsets: list[int]
	param_offsets: list[int]


@dataclass
class SleepingLogic:
	logic: ActLogic
	logic_pointer_offset: int
	logic_offset: int
	param_offsets: list[int]


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
	elif value.startswith("0x") and len(value)>4:
		return "bytes"
	elif value.startswith("0x") and len(value)<=4:
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
			print("Warning: Unable to identify type of '{0}'.".format(my_title))
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


def add_string_variable(new_sv):
	match = False
	for sv in string_variables:
		if new_sv.string == sv.string:
			match = True
			for sl in new_sv.source_logics:
				sv.source_logics.append(sl)
			break
	if not match:
		string_variables.append(new_sv)


def add_group_variable(new_gv):
	match = False
	'''
	for gv in group_variables:
		pass
		if new_gv.string == sv.string:
			match = True
			for sl in new_gv.source_logics:
				sv.source_logics.append(sl)
			break
	'''
	if not match:
		group_variables.append(new_gv)


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
	

def gather_strings(owner, logic_tree):
	my_logic = logic_tree
	my_type = my_logic.type
	my_value = my_logic.value
	my_value_type = my_logic.value_type
	if my_value_type == "string":
		# Remove quotes
		if my_value.startswith('\"'):
			my_value = my_value[1:-1]
		if my_value.startswith('h\"'):
			my_value = my_value[2:-1]
		# Check if any remaining string before continuing
		if len(my_value):
			if owner.title == "FileReference":
				# Add to string variables
				match = False
				for s in reference_strings:
					if s.string == my_value:
						s.source_logics.append(my_logic)
						match = True
				if not match:
					sv = LogicStringVariable(None, my_value, [])
					reference_strings.append(sv)
			else:
				# Add to string variables
				match = False
				for s in string_variables:
					if s.string == my_value:
						s.source_logics.append(my_logic)
						match = True
				if not match:
					# Warning: Only add string if db param type is 'string'
					# Some string values such as param00024 from track Animation
					# must always be stored as a hash, they do not work when using 'string variables'
					# Node paths however must be kept only as 'string variables'
					param_match = match_param_database(owner.title, my_logic, db_conditions + db_tracks)
					if param_match:
						# Param match, only add string variable if type string
						if param_match.type in ("string"):
							sv = LogicStringVariable(None, my_value, [my_logic])
							add_string_variable(sv)
					else:
						# No param match
						# This should case no problems now that hashed strings start with 'h'
						sv = LogicStringVariable(None, my_value, [my_logic])
						add_string_variable(sv)
	for c in my_logic.conditions + my_logic.tracks + my_logic.params + my_logic.children:
		gather_strings(my_logic, c)


def write_string_variables(file):
	for var in string_variables:
		my_string = var.string
		my_string_offset = file.tell()
		var_param_offsets = []
		format_write(file, 0, "I")
		format_write(file, len(var.source_logics), "H")
		for source in var.source_logics:
			var_param_offsets.append(file.tell())
			format_write(file, 0, "I")
		ss = SleepingString(my_string, [my_string_offset], [], var_param_offsets, [])
		offset_manager.add_sleeping_string(ss)


def gather_groups(owner, logic_tree):
	my_logic = logic_tree
	for c in my_logic.conditions + my_logic.tracks + my_logic.params + my_logic.children:
		if c.type == "Param" and len(c.children):
			# print(c.value, c.type, len(c.conditions), len(c.tracks), len(c.params), len(c.children))
			# populated group
			gv = LogicGroupVariable(None, [c])
			add_group_variable(gv)
	for c in my_logic.conditions + my_logic.tracks + my_logic.params + my_logic.children:
		gather_groups(my_logic, c)


def write_group_variables(file):
	for var in group_variables:
		my_group_offset = file.tell()
		var_param_offsets = []
		format_write(file, 0, "I")
		format_write(file, len(var.source_logics), "H")
		for source in var.source_logics:
			var_param_offsets.append(file.tell())
			format_write(file, 0, "I")
		# I'll just lazily take the last source here
		# No group optimization whatsoever
		sg = SleepingGroup(source, my_group_offset, None, [], [], var_param_offsets, [])
		offset_manager.add_sleeping_group(sg)


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
		ss = SleepingString(file_name, [my_offset], [], [], [])
		offset_manager.add_sleeping_reference_string(ss)
		ss = SleepingString(file_path, [my_offset+4], [], [], [])
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
			sl = SleepingLogic(c, my_offset, None, None)
			offset_manager.add_sleeping_condition(sl)
			# Write padding
			format_write(file, 0, "I")
	# print tracks
	if my_type in ('Node'):
		format_write(file, number_of_tracks, "B")
		for t in my_logic.tracks:
			# Set up sleeping track
			my_offset = file.tell()
			sl = SleepingLogic(t, my_offset, None, [])
			offset_manager.add_sleeping_track(sl)
			# Write padding
			format_write(file, 0, "I")
	# print number of children
	if my_type in ('Bank', 'Node'):
		format_write(file, number_of_children, "H")
	# call recursion
	for c in my_logic.children:
		write_cat_tree(file, c)
	

def write_param_value_by_param_type(file, param, db_param_type):
	value = param.value
	value_type = param.value_type
	# temporary jank fix for params that need to be stored as hash
	# such as param00024 from Animation (t-pose otherwise)
	if value_type == "string" and db_param_type == "bytes":
		if value.startswith('\"'):
			value = value[1:-1]
		match = False
		for ss in offset_manager.sleeping_strings:
			if ss.string == value:
				match = True
				ss.param_offsets.append(file.tell())
		hash = hash_cat_value(value)
		file.write(hash)
		return
	if value_type != "unk" and value_type != db_param_type:
		print("Warning: Database thinks param '{0}' value '{1}' is '{2}' but value type is '{3}', perhaps the templates are incorrect, value will be treated as type '{3}'.".format(param.title, param.value, db_param_type, value_type))
		db_param_type = value_type
	if db_param_type == "bytes":
		value = value[2:]
		try:
			value = bytearray.fromhex(value)
		except:
			print("Error: Mismatched param type '{0}' on value '{1}', expected bytes. Writing zero. (Try generating templates)".format(param.value_type, param.value))
			value = bytearray.fromhex("00000000")
		file.write(value)
	elif db_param_type == "int":
		format_write(file, int(value), "i")
	elif db_param_type == "bool":
		string = str(value).upper()
		if '1' in string or "TRUE" in string:
			format_write(file, 1, "B")
		else:
			format_write(file, 0, "B")
	elif db_param_type == "float":
		format_write(file, float(value), "f")
	elif db_param_type == "string":
		# Try to match with sleeping strings first
		if value.startswith('\"'):
			value = value[1:-1]
		match = False
		for ss in offset_manager.sleeping_strings:
			if ss.string == value:
				match = True
				ss.param_offsets.append(file.tell())
		if match:
			format_write(file, 0, "I")
		else:
			hash = hash_cat_value(value)
			file.write(hash)
	elif db_param_type == "hashed_string":
		# Remove 'h' and quotes from string
		if value.startswith('h\"'):
			value = value[2:-1]
		hash = hash_cat_value(value)
		file.write(hash)
	elif db_param_type == "cg":
		# Ignore CG if no children (should have conditions -- verify later)
		if not len(param.children):
			format_write(file, 0, "I")
		else:	
			# Match with sleeping groups
			match = False
			safe_pos = file.tell()
			# Store CG offsets to be used by fix_group_offsets -- fix jank later
			for sg in offset_manager.sleeping_groups:
				if sg.logic_node == param:
					# We'll check if enough pointer_offsets in this SG before appending
					# so that one single repeated thing doesn't eat all the offsets
					len1 = len(sg.var_param_offsets)
					len2 = len(sg.param_offsets)
					if len1 > len2:
						match = True
						sg.param_offsets.append(safe_pos)
						break
			if not match:
				print("Warning: Unable to match param '{0}' to variable condition group.".format(param.title))
			format_write(file, 0, "I")
	elif db_param_type == "none":
		print("Warning: Param {0} has value type none.".format(param.title))
		format_write(file, 0, "I")
	else:
		print("Error: Unable to handle param type '{0}' on value '{1}', writing value zero.".format(param.value_type, param.value))
		format_write(file, 0, "I")


def write_param_data(file, logic_tree):
	for sl in offset_manager.sleeping_conditions+offset_manager.sleeping_group_conditions:
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Write pointer
		file.seek(sl.logic_pointer_offset, 0)
		format_write(f_cat, safe_pos - p_data, "I")
		file.seek(safe_pos)
		# Write condition hash
		hashed_title = hash_cat_value(sl.logic.title)
		file.write(hashed_title)
		# Write params
		number_of_params = len(sl.logic.params)
		for logic_param in sl.logic.params:
			param_id = get_param_id_from_param_title(logic_param)
			param_match = match_param_database(sl.logic.title, logic_param, db_conditions)
			if param_match:
				# Write param value using database match's type
				write_param_value_by_param_type(file, logic_param, param_match.type)
			else:
				# Write param value using logic param's type
				print_debug(
					"Warning: No matching param ID: {0} in param database.".format(param_id))
				write_param_value_by_param_type(file, logic_param, logic_param.value_type)
	for sl in offset_manager.sleeping_tracks:
		safe_pos = file.tell()
		sl.logic_offset = safe_pos
		# Write pointer
		file.seek(sl.logic_pointer_offset, 0)
		format_write(f_cat, safe_pos - p_data, "I")
		file.seek(safe_pos)
		# Write track hash
		format_write(file, 0, "H")  # opti offset
		hashed_title = hash_cat_value(sl.logic.title)
		param_id = 0
		param_id |= 0x0004
		if len(sl.logic.params):
			param_id |= 0x0001
		format_write(file, param_id, "H")
		file.write(hashed_title)
		# Write params
		number_of_params = len(sl.logic.params)
		for i, logic_param in enumerate(sl.logic.params):
			param_id = get_param_id_from_param_title(logic_param)
			param_match = match_param_database(sl.logic.title, logic_param, db_tracks)
			# Write param flags
			if param_match:
				param_id = int(param_match.id)
				param_id <<= 3
				if(param_match.type != 'bool'):
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
			if(i < number_of_params-1):
				param_id |= 0x0001
			# Write param id
			format_write(file, param_id, "H")
			# Write param value
			if param_match:
				# Write param value using database match's type
				write_param_value_by_param_type(file, logic_param, param_match.type)
			else:
				# Write param value using logic param's type
				print_debug(
					"Warning: No matching param ID: {0} in param database.".format(param_id))
				write_param_value_by_param_type(file, logic_param, logic_param.value_type)


def _write_strings(file, sleeping_list):
	for s in sleeping_list:
		safe_pos = file.tell()
		my_offset = safe_pos - p_strings
		# Write my_offset on var_string_offsets
		# (Multiple offsets required because of 'FileReference')
		for vso in s.var_string_offsets:
			file.seek(vso, 0)
			format_write(file, my_offset, "I")
		# Write param_offsets on var_param_offsets
		len1 = len(s.var_param_offsets)
		len2 = len(s.param_offsets)
		if len1 != len2:
			print("Warning: Mismatching number of var_param_offsets {0} and param_offsets {1} for {2}.".format(len1, len2, s.string))
		if len1 >= len2:
			for i, po in enumerate(s.param_offsets):
				param_safe_pos = file.tell()
				var_pos = s.var_param_offsets[i]
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
		# Write my_offset on var_group_offset
		file.seek(g.var_group_offset)
		format_write(file, my_offset, "I")
		# Write number of conditions
		file.seek(safe_pos, 0)
		format_write(file, len(g.logic_node.children), "B")
		# Write padding for each condition offset and add extra sleeping conditions
		# since these conditions are not listed within the node tree
		for c in g.logic_node.children:
			condition_pointer_offset = file.tell()
			g.var_condition_offsets.append(condition_pointer_offset)
			format_write(file, 0, "I")
			sl = SleepingLogic(c, condition_pointer_offset, None, None)
			offset_manager.add_sleeping_group_condition(sl)


def fix_group_offsets(file):
	safe_pos = file.tell()
	debug_counter = 0

	# this list is a fix so that different groups with identical conditions
	# don't all hoard the first identical condition and ignore the repeats
	used_condition_offsets = []
	for group in offset_manager.sleeping_groups:
		# Run through all sleeping conditions
		# Check which ones are used in condition groups
		# Append their offset to their corresponding groups
		for sgc in group.logic_node.children:
			# sgc is a condition of this group node
			for sl in offset_manager.sleeping_group_conditions:
				if sgc == sl.logic:
					if sl.logic_offset not in used_condition_offsets:
						used_condition_offsets.append(sl.logic_offset)
						group.condition_offsets.append(sl.logic_offset)
						break
		# Write condition offsets into condition pointer offsets
		len1 = len(group.var_condition_offsets)
		len2 = len(group.condition_offsets)
		if len1 != len2:
			print("Warning: Mismatching number of condition_pointer_offsets {0} and condition_offsets {1}.".format(len1, len2))
		if len1 >= len2:
			for i, po in enumerate(group.condition_offsets):
				param_safe_pos = file.tell()
				var_pos = group.var_condition_offsets[i]
				file.seek(var_pos)
				format_write(file, po - p_data, "I")
				file.seek(param_safe_pos)
		# Write param offsets into param pointer offsets
		len1 = len(group.var_param_offsets)
		len2 = len(group.param_offsets)
		if len1 != len2:
			print("Warning: Mismatching number of param_pointer_offsets {0} and param_offsets {1}.".format(len1, len2))
			# print("VPO: ", group.var_param_offsets)
			# print("PO: ", group.param_offsets)
			# print(group)
		if len1 >= len2:
			for i, po in enumerate(group.param_offsets):
				param_safe_pos = file.tell()
				var_pos = group.var_param_offsets[i]
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
		if len(my_line)==0 or l[0] == '#':
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
string_variables = []
group_variables = []
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

	conditions, tracks = gather_logic(logic_nodes)
	gather_strings(None, logic_tree)
	gather_groups(None, logic_tree)

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
	write_param_data(f_cat, logic_tree)

	## STRINGS ##
	print("->-> Writing string data.")
	p_strings = f_cat.tell()
	write_strings(f_cat)
	write_reference_strings(f_cat)

	## FIX HEADER & OFFSETS ##
	print("->-> Fixing offsets.")
	file_length = f_cat.tell()
	fix_group_offsets(f_cat) # fix var param group offsets
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
	format_write(f_cat, len(string_variables), "I")  # number_of_strings_vars
	f_cat.seek(p_var_groups, 0)
	format_write(f_cat, len(group_variables), "I") # number_of_groups_vars
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


# End #
print("Done.")
quit()
