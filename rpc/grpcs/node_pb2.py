# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: protos/node.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x11protos/node.proto\"\x0f\n\rStatusRequest\"\xb3\x02\n\rStatusRespond\x12\x13\n\x06height\x18\x01 \x01(\x05H\x00\x88\x01\x01\x12\x1f\n\x12vote_center_height\x18\x02 \x01(\x05H\x01\x88\x01\x01\x12\x18\n\x0bpool_height\x18\x03 \x01(\x05H\x02\x88\x01\x01\x12\x18\n\x0bpool_counts\x18\x04 \x01(\x05H\x03\x88\x01\x01\x12\x19\n\x0cgossip_queue\x18\x05 \x01(\x05H\x04\x88\x01\x01\x12\x16\n\tvalid_txs\x18\x06 \x01(\x05H\x05\x88\x01\x01\x12\x16\n\tvote_info\x18\x07 \x01(\tH\x06\x88\x01\x01\x42\t\n\x07_heightB\x15\n\x13_vote_center_heightB\x0e\n\x0c_pool_heightB\x0e\n\x0c_pool_countsB\x0f\n\r_gossip_queueB\x0c\n\n_valid_txsB\x0c\n\n_vote_info\"\x11\n\x0fStopNodeRequest\"\x11\n\x0fStopNodeRespond2j\n\x04Node\x12\x31\n\x0fget_node_status\x12\x0e.StatusRequest\x1a\x0e.StatusRespond\x12/\n\tstop_node\x12\x10.StopNodeRequest\x1a\x10.StopNodeRespondb\x06proto3')



_STATUSREQUEST = DESCRIPTOR.message_types_by_name['StatusRequest']
_STATUSRESPOND = DESCRIPTOR.message_types_by_name['StatusRespond']
_STOPNODEREQUEST = DESCRIPTOR.message_types_by_name['StopNodeRequest']
_STOPNODERESPOND = DESCRIPTOR.message_types_by_name['StopNodeRespond']
StatusRequest = _reflection.GeneratedProtocolMessageType('StatusRequest', (_message.Message,), {
  'DESCRIPTOR' : _STATUSREQUEST,
  '__module__' : 'protos.node_pb2'
  # @@protoc_insertion_point(class_scope:StatusRequest)
  })
_sym_db.RegisterMessage(StatusRequest)

StatusRespond = _reflection.GeneratedProtocolMessageType('StatusRespond', (_message.Message,), {
  'DESCRIPTOR' : _STATUSRESPOND,
  '__module__' : 'protos.node_pb2'
  # @@protoc_insertion_point(class_scope:StatusRespond)
  })
_sym_db.RegisterMessage(StatusRespond)

StopNodeRequest = _reflection.GeneratedProtocolMessageType('StopNodeRequest', (_message.Message,), {
  'DESCRIPTOR' : _STOPNODEREQUEST,
  '__module__' : 'protos.node_pb2'
  # @@protoc_insertion_point(class_scope:StopNodeRequest)
  })
_sym_db.RegisterMessage(StopNodeRequest)

StopNodeRespond = _reflection.GeneratedProtocolMessageType('StopNodeRespond', (_message.Message,), {
  'DESCRIPTOR' : _STOPNODERESPOND,
  '__module__' : 'protos.node_pb2'
  # @@protoc_insertion_point(class_scope:StopNodeRespond)
  })
_sym_db.RegisterMessage(StopNodeRespond)

_NODE = DESCRIPTOR.services_by_name['Node']
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  _STATUSREQUEST._serialized_start=21
  _STATUSREQUEST._serialized_end=36
  _STATUSRESPOND._serialized_start=39
  _STATUSRESPOND._serialized_end=346
  _STOPNODEREQUEST._serialized_start=348
  _STOPNODEREQUEST._serialized_end=365
  _STOPNODERESPOND._serialized_start=367
  _STOPNODERESPOND._serialized_end=384
  _NODE._serialized_start=386
  _NODE._serialized_end=492
# @@protoc_insertion_point(module_scope)
