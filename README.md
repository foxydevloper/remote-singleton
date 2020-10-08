# remote_singleton
This module allows the ability to make it so specified functions only run on a single process.
Using the @Singleton.run_on decorator on a function will specify it should run on the singleton.
Anything that runs the function will end up running it on the singleton's process.
The process which runs singleton.start() will be the process that handles all the functions for that singleton.

A module must be created which will serve as a gateway between the singleton's process and the processes (or even other machines) which desire to run the functions on the other process. Running singleton.start() should only be done on a single process.
### my_singleton.py
```py
from remote_singleton import ExampleSingleton

singleton = ExampleSingleton()

@singleton.run_on
def run_on_singleton(ran_file):
    print(f"This function was ran on {__file__} by {ran_file}")
    return f"Hello {ran_file} from {__file__}"

if __name__ == "__main__":
    singleton.start()
```
Now, in another module, you run the function on the singleton by just running the function normally
### worker.py
```py
import my_singleton

response = my_singleton.run_on_singleton(__file__)
print(response)
```
This would print `"This function was ran on my_singleton.py by worker.py"` on the singleton, and would print `"Hello worker.py from my_singleton.py"` on the process which called the function

# Hiding code from client

If you wanted to have it so clients wouldn't need the code that the remote singleton calls when invoked, you could seperate the client and the server as so:
### my_singleton_dummy.py
```py
from remote_singleton import ExampleSingleton

singleton = ExampleSingleton()

@singleton.run_on
def run_on_singleton(ran_file):
  pass  # Client is not able to see the code for the function
```
### my_singleton_server.py
```py
from my_singleton_dummy import singleton

@singleton.run_on
def run_on_singleton(ran_file):  # Since we've already declared this function before in the dummy,
                                 # it will be overwritten with the new code
    print(f"This function was ran on {__file__} by {ran_file}")
    return f"Hello {ran_file} from {__file__}"

if __name__ == '__main__':
    singleton.start()
```

This means that a client could run the remote function as so:
### worker.py
```py
import my_singleton_dummy

response = my_singleton.run_on_singleton(__file__)
print(response)
```
This would still print `"This function was ran on my_singleton.py by worker.py"` on the singleton, and `"Hello worker.py from my_singleton.py"` on the process which called the function, even though the client is unable to see the code

Currently, this supports using rpyc as the transportation method and pickle for the serialization. `RpycSingleton` takes a dict parameter `rpyc_server_config` which just gets passed to the rpyc's connect()'s config, allowing you to change `hostname` and `port`, or `socket_path`
```py
RpycSingleton(rpyc_server_config={
    'host': 'localhost',
    'port': 8312,
    #'socket_path': 'singleton.sock'
})
```
