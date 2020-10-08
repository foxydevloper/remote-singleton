
import pickle
import rpyc
from dataclasses import dataclass, field
from typing import Optional
import os

"""
This module allows the ability to make it so specified functions only run on a single machine.
Using the run_on_singleton operator on a function will specify it should run on the singleton.
Anything that runs the function will end up running it on the singleton.
The singleton can be initiated by using start()
"""


# TODO: Add support for swapping out transport method, for example ability to use socketio or something
# TODO: Add support for different serializers
# TODO: Open source


class BaseSerializer:
    @staticmethod
    def client_wrapper():
        raise NotImplementedError

    @staticmethod
    def server_wrapper():
        raise NotImplementedError


# To be fair I don't know how to make an interface in python
class BaseSingleton:
    serializer: BaseSerializer

    def run_on(self, func):
        raise NotImplementedError

    def start(self):
        raise NotImplementedError


class PickleSerializer(BaseSerializer):
    @staticmethod
    def client_wrapper(func):
        def wrapped(*args, **kwargs):
            unpickled_args = map(lambda arg: pickle.dumps(arg), args)
            unpickled_kwargs = {k: pickle.dumps(v) for k, v in kwargs.items()}
            try:
                return pickle.loads(func(*unpickled_args, **unpickled_kwargs))
            except TypeError:  # No result received
                pass
        return wrapped

    @staticmethod
    def server_wrapper(func):
        def wrapped(self, *args, **kwargs):  # We include self since we are adding the function to BackendService, and we don't need self.
            pickled_args = map(lambda arg: pickle.loads(arg), args)
            pickled_kwargs = {k: pickle.loads(v) for k, v in kwargs.items()}
            try:
                return pickle.dumps(func(*pickled_args, **pickled_kwargs))
            except AttributeError:  # No result
                pass
        return wrapped


@dataclass
class RpycSingleton(BaseSingleton):
    rpyc_server_config: dict = field(default_factory=lambda: {'socket_path': "manager.sock"})  # Singleton will communicate over a unix socket by default
    serializer: Optional[BaseSerializer] = PickleSerializer

    def __post_init__(self):
        class SingletonService(rpyc.Service):  # Create a new blank rpyc service
            pass
        self.rpyc_service = SingletonService

    def connect(self):
        "Connect to the singleton's rpyc service"
        if 'socket_path' in self.rpyc_server_config:
            socket_path = self.rpyc_server_config['socket_path']
            return rpyc.utils.factory.unix_connect(socket_path)
        else:
            host, port = self.rpyc_server_config['hostname'], self.rpyc_server_config['port']
            return rpyc.utils.factory.connect(host, port)

    def run_on(self, func):
        """
        This wrapper will make the specified function run on the singleton.
        It will overwrite the function given with a new function that remotely calls the function through rpyc.

        I can't even tell if this is a botch. This is literally just beautiful.
        I don't have to write two functions for every single remotely called function I want to add.
        """

        if self.serializer:
            wrapped_func = self.serializer.server_wrapper(func)

        setattr(self.rpyc_service, f'exposed_{func.__name__}', wrapped_func or func)  # Add the function to the BackendService

        def client_func(*args, **kwargs):  # Create a client sided version that just remotely calls through rpyc
            with self.connect() as singleton_conn:
                return getattr(singleton_conn.root, func.__name__)(*args, **kwargs)

        if self.serializer:
            wrapped_client_func = self.serializer.client_wrapper(client_func)

        return wrapped_client_func or client_func

    def start(self):
        """
        This function should be called from the __main__ script.
        Whichever process calls this will be the process that hosts the singleton.
        """
        if 'socket_path' in self.rpyc_server_config:
            try:
                os.remove(self.rpyc_server_config['socket_path'])
            except OSError:
                pass
        conn = rpyc.utils.server.ThreadedServer(self.rpyc_service, **self.rpyc_server_config)
        conn.start()
