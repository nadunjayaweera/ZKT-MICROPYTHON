from zk_main import ZKLib

async def test():
    zk_instance = ZKLib("192.168.1.235", 4370, 10000, 4000)
    try:
        # Create socket to machine
        await zk_instance.create_socket()

        # Get general info like logCapacity, user counts, logs count
        # It's really useful to check the status of the device
        print(await zk_instance.get_info())
    except Exception as e:
        print("Error:", e)

    # Uncomment these lines if you need to retrieve users or attendances
    # users = await zk_instance.get_users()
    # print(len(users['data']))

    # device_id = await zk_instance.get_device_id()
    # print(device_id)

    # attendances = await zk_instance.get_attendances()
    # print(attendances['data'])

    users = await zk_instance.get_users()
    print(users['data'])

# Run the test function
test()
