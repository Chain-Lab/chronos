# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: rpc/protos/block.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x16rpc/protos/block.proto\"m\n\x0c\x42lockRequest\x12\x18\n\x04type\x18\x01 \x01(\x0e\x32\x05.TypeH\x00\x88\x01\x01\x12\x13\n\x06height\x18\x02 \x01(\x03H\x01\x88\x01\x01\x12\x11\n\x04hash\x18\x03 \x01(\tH\x02\x88\x01\x01\x42\x07\n\x05_typeB\t\n\x07_heightB\x07\n\x05_hash\"L\n\x0c\x42lockRespond\x12\x13\n\x06status\x18\x01 \x01(\x05H\x00\x88\x01\x01\x12\x12\n\x05\x62lock\x18\x02 \x01(\tH\x01\x88\x01\x01\x42\t\n\x07_statusB\x08\n\x06_block*(\n\x04Type\x12\n\n\x06HEIGHT\x10\x00\x12\x08\n\x04HASH\x10\x01\x12\n\n\x06LATEST\x10\x02\x32\x32\n\x05\x42lock\x12)\n\tget_block\x12\r.BlockRequest\x1a\r.BlockRespondb\x06proto3')

_TYPE = DESCRIPTOR.enum_types_by_name['Type']
Type = enum_type_wrapper.EnumTypeWrapper(_TYPE)
HEIGHT = 0
HASH = 1
LATEST = 2


_BLOCKREQUEST = DESCRIPTOR.message_types_by_name['BlockRequest']
_BLOCKRESPOND = DESCRIPTOR.message_types_by_name['BlockRespond']
BlockRequest = _reflection.GeneratedProtocolMessageType('BlockRequest', (_message.Message,), {
  'DESCRIPTOR' : _BLOCKREQUEST,
  '__module__' : 'rpc.protos.block_pb2'
  # @@protoc_insertion_point(class_scope:BlockRequest)
  })
_sym_db.RegisterMessage(BlockRequest)

BlockRespond = _reflection.GeneratedProtocolMessageType('BlockRespond', (_message.Message,), {
  'DESCRIPTOR' : _BLOCKRESPOND,
  '__module__' : 'rpc.protos.block_pb2'
  # @@protoc_insertion_point(class_scope:BlockRespond)
  })
_sym_db.RegisterMessage(BlockRespond)

_BLOCK = DESCRIPTOR.services_by_name['Block']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _TYPE._serialized_start=215
  _TYPE._serialized_end=255
  _BLOCKREQUEST._serialized_start=26
  _BLOCKREQUEST._serialized_end=135
  _BLOCKRESPOND._serialized_start=137
  _BLOCKRESPOND._serialized_end=213
  _BLOCK._serialized_start=257
  _BLOCK._serialized_end=307
# @@protoc_insertion_point(module_scope)
