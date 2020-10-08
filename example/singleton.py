
from remote_singleton import RpycSingleton

singleton = RpycSingleton(rpyc_server_config={
    'hostname': 'localhost',
    'port': 8231
})


@singleton.run_on
def run_on_singleton(ran_file):
    print(f"This function was ran on {__file__} by {ran_file}")


if __name__ == "__main__":
    singleton.start()
