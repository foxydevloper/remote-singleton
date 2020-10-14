
import pickle
import rpyc
from dataclasses import dataclass
from typing import Optional, Type
import os


# TODO: Add support for swapping out transport method, for example ability to use socketio or something
# TODO: Add support for different serializers
# TODO: Asyncio support for running the functions?
# TODO: Ability to disable serialization when coming from client,
#       or having a different serializer for the client
#       for security


class BaseSerializer:
    @staticmethod
    def client_wrapper():
        raise NotImplementedError

    @staticmethod
    def server_wrapper():
        raise NotImplementedError


# To be fair I don't know how to make an interface in python
class BaseSingleton:
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
        def wrapped(*args, **kwargs):
            pickled_args = map(lambda arg: pickle.loads(arg), args)
            pickled_kwargs = {k: pickle.loads(v) for k, v in kwargs.items()}
            try:
                return pickle.dumps(func(*pickled_args, **pickled_kwargs))
            except AttributeError:  # No result
                pass
        return wrapped


@dataclass
class RpycSingleton(BaseSingleton):
    rpyc_server_config: dict
    serializer: Optional[Type[BaseSerializer]] = PickleSerializer

    def __post_init__(self):
        class SingletonService(rpyc.Service):  # Create a new blank rpyc service
            pass
        self.rpyc_service = SingletonService

    def connect(self):
        "Connect to the singleton's rpyc service"
        try:
            if 'socket_path' in self.rpyc_server_config:
                socket_path = self.rpyc_server_config['socket_path']
                return rpyc.utils.factory.unix_connect(socket_path)
            else:
                host, port = self.rpyc_server_config['hostname'], self.rpyc_server_config['port']
                return rpyc.utils.factory.connect(host, port)
        except (FileNotFoundError):  # TODO: Add support for host-port failures aswell
            raise Exception("Singleton is not running")  # TODO: Be more descriptive?

    def run_on(self, func):
        """
        This decorator will make the specified function run on the singleton.
        It will overwrite the function given with a new function that remotely calls the function through rpyc.
        """
        func_name = func.__name__

        server_func = func
        if self.serializer:
            server_func = self.serializer.server_wrapper(server_func)

        def server_func(self, *args, **kwargs):  # HACK: rpyc service includes an unneccessary self parameter we want to remove
            return server_func(*args, **kwargs)

        setattr(self.rpyc_service, f'exposed_{func_name}', server_func)  # Add the function to the BackendService

        def client_func(*args, **kwargs):  # Create a client sided version that just remotely calls through rpyc
            with self.connect() as singleton_conn:
                return getattr(singleton_conn.root, func_name)(*args, **kwargs)

        if self.serializer:
            client_func = self.serializer.client_wrapper(client_func)

        return client_func

    def start(self):
        """
        This function should be called from the __main__ script.
        Whichever process calls this will be the process that hosts the singleton.
        """
        if 'socket_path' in self.rpyc_server_config:
            try:
                os.remove(self.rpyc_server_config['socket_path'])  # This is a botch, sometimes rpyc messes up when path already exists
            except OSError:
                pass
        conn = rpyc.utils.server.ThreadedServer(self.rpyc_service, **self.rpyc_server_config)
        conn.start()
