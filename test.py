import asyncio
from zk_main import ZKLIB

async def test():
    zk_instance = ZKLIB("192.168.1.235", 4370, 10000, 4000)
    try:
        # Create socket to machine
        zk_instance.create_socket()

        # Get general info like logCapacity, user counts, logs count
        print("Device Info:", zk_instance.get_info())

        # Retrieve attendances
        # attendances = zk_instance.get_attendances(cb=None)  # No callback needed
        # print("Attendances:", attendances['data'])

        # Retrieve users
        users = zk_instance.get_users()
        print("User Details:", users['data'])

    except Exception as e:
        print("Error:", e)
    finally:
        # Disconnect from the device
        zk_instance.disconnect()

# Run the test function
if __name__ == "__main__":
    asyncio.run(test())
