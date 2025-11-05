#!/usr/bin/env python3
"""
Identify which ESC you're monitoring by testing each throttle slot.

This will help determine:
1. Which of the 4 throttle slots this ESC responds to
2. Which motor number (1-8) this ESC controls
3. Whether the ESC uses multiple slots

Usage: python3 identify_esc.py /dev/cu.usbmodem14201
"""

import sys
import time
from test_throttle import DJIThrottleController

def test_slot(controller, slot_num, test_throttle=1500):
    """
    Test a specific throttle slot to see if motor responds.

    Args:
        controller: DJIThrottleController instance
        slot_num: Which slot to test (1-4)
        test_throttle: Throttle value to apply
    """
    # Idle values for all slots
    idle_values = [7, 0, 944, 0]

    # Set test throttle for the specified slot
    test_values = idle_values.copy()
    test_values[slot_num - 1] = test_throttle

    print(f"\n{'='*70}")
    print(f"TESTING SLOT {slot_num}")
    print(f"{'='*70}")
    print(f"Throttle values: Slot1={test_values[0]}, Slot2={test_values[1]}, "
          f"Slot3={test_values[2]}, Slot4={test_values[3]}")
    print(f"\nSlot {slot_num} = {test_throttle}")
    print(f"\n⚠️  WATCH/LISTEN for motor response!")
    print(f"    - Motor spinning?")
    print(f"    - Beeping/clicking?")
    print(f"    - Any change in sound?")

    input("\nPress ENTER when ready to apply throttle...")

    # Apply throttle for 3 seconds
    print(f"\nApplying throttle to slot {slot_num} for 3 seconds...")
    controller.set_throttle(*test_values, duration=3.0)

    # Return to idle
    print("Returning to idle...")
    controller.set_throttle(*idle_values, duration=1.0)

    response = input(f"\nDid motor respond to slot {slot_num}? (yes/no/unsure): ").strip().lower()
    return response == 'yes'

def main():
    print("=" * 80)
    print("ESC IDENTIFICATION TEST")
    print("=" * 80)
    print()
    print("This will test each of the 4 throttle slots to determine which")
    print("slot controls the motor on the ESC you're monitoring.")
    print()
    print("⚠️  SAFETY CHECKLIST:")
    print("   ✓ NO PROPELLERS attached")
    print("   ✓ ESC/motor secured to bench")
    print("   ✓ Battery connected and charged")
    print("   ✓ Emergency stop plan ready")
    print()

    if len(sys.argv) < 2:
        print("Usage: python3 identify_esc.py <serial_port>")
        print("Example: python3 identify_esc.py /dev/cu.usbmodem14201")
        sys.exit(1)

    port = sys.argv[1]

    ready = input("Ready to begin? (yes/no): ").strip().lower()
    if ready != 'yes':
        print("Aborted.")
        sys.exit(0)

    # Connect
    controller = DJIThrottleController(port)
    if not controller.connect():
        print("Failed to connect. Exiting.")
        sys.exit(1)

    try:
        # Arm the ESC
        print("\n" + "=" * 80)
        print("STEP 1: ARMING ESC")
        print("=" * 80)
        controller.arm()
        print("\n✓ ESC should be armed now (listen for beep-beep-beep)")
        time.sleep(2)

        # Test each slot
        results = {}

        for slot in [1, 2, 3, 4]:
            responded = test_slot(controller, slot, test_throttle=1500)
            results[slot] = responded

            if responded:
                print(f"\n✓ SLOT {slot} CONTROLS THIS MOTOR!")
            else:
                print(f"\n✗ Slot {slot} - No response")

            time.sleep(1)

        # Summary
        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)

        responding_slots = [slot for slot, responded in results.items() if responded]

        if len(responding_slots) == 0:
            print("\n⚠️  NO SLOTS RESPONDED")
            print("\nPossible issues:")
            print("  1. ESC not properly armed")
            print("  2. Wrong baud rate or wiring issue")
            print("  3. This ESC uses a different slot assignment")
            print("  4. Test throttle value too low (try higher)")
            print("  5. Motor/ESC issue")

        elif len(responding_slots) == 1:
            slot = responding_slots[0]
            print(f"\n✓ THIS ESC USES SLOT {slot}")
            print(f"\nThis means:")
            print(f"  - This ESC listens to bytes [{(slot-1)*2 + 2}:{(slot-1)*2 + 3}] in the payload")

            if slot == 1:
                print(f"  - Payload bytes [2:3]")
            elif slot == 2:
                print(f"  - Payload bytes [6:7]")
            elif slot == 3:
                print(f"  - Payload bytes [8:9]")
                print(f"  - NOTE: This slot had voltage (944) at idle!")
            elif slot == 4:
                print(f"  - Payload bytes [10:11]")

            print(f"\nSince the T40 has 8 motors and we see 4 slots:")
            print(f"  - ESCs 1-4 use slots 1-4 on one bus")
            print(f"  - ESCs 5-8 use slots 1-4 on another bus (or same bus, different frames)")
            print(f"  - Your ESC is one of motors 1-4 (or 5-8), specifically slot {slot}")

        else:
            print(f"\n⚠️  MULTIPLE SLOTS RESPONDED: {responding_slots}")
            print("\nThis is unexpected. Possibilities:")
            print("  1. Multiple motors connected to this ESC")
            print("  2. Cross-talk or electrical interference")
            print("  3. ESC using complex addressing")

        # Disarm
        print("\n" + "=" * 80)
        print("DISARMING ESC")
        print("=" * 80)
        controller.disarm()

    except KeyboardInterrupt:
        print("\n\n!!! INTERRUPTED - DISARMING !!!")
        controller.disarm()

    finally:
        controller.disconnect()

if __name__ == '__main__':
    main()
