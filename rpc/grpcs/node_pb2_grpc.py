# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

from rpc.grpcs import node_pb2 as node__pb2


class NodeStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.get_node_status = channel.unary_unary(
                '/Node/get_node_status',
                request_serializer=node__pb2.StatusRequest.SerializeToString,
                response_deserializer=node__pb2.StatusRespond.FromString,
                )


class NodeServicer(object):
    """Missing associated documentation comment in .proto file."""

    def get_node_status(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_NodeServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'get_node_status': grpc.unary_unary_rpc_method_handler(
                    servicer.get_node_status,
                    request_deserializer=node__pb2.StatusRequest.FromString,
                    response_serializer=node__pb2.StatusRespond.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'Node', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class Node(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def get_node_status(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/Node/get_node_status',
            node__pb2.StatusRequest.SerializeToString,
            node__pb2.StatusRespond.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
