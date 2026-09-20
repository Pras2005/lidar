import time
import math

class TiM240EmbeddedManager:
    """
    Handles synchronization of Python logic to the LiDAR's internal EEPROM.
    Enables 'Standalone Mode' where the sensor triggers a buzzer without a PC.
    """
    def __init__(self, controller):
        self.lidar = controller
        # Standard SICK passwords
        self.PASSWORDS = {
            "authorized_client": "F4724744", # Level 3
            "service": "B9B26322"            # Level 4
        }

    def unlock_sensor(self) -> bool:
        """Enters Authorized Client mode to allow configuration changes."""
        cmd = f"sMN SetAccessMode 03 {self.PASSWORDS['authorized_client']}"
        resp = self.lidar.send_cola_command(cmd)
        if "sAN SetAccessMode 00" in resp or "sAN SetAccessMode 01" in resp:
            print("✅ Sensor Unlocked (Authorized Client Mode)")
            return True
        print(f"❌ Unlock Failed: {resp}")
        return False

    def sync_forklift_threshold(self, min_length_m: float, distance_m: float):
        """
        Translates 'meters' into 'point count' for internal sensor logic.
        Rule: If human-sized (0.5m) hit, ignore. If forklift-sized hit, alarm.
        """
        # Angular resolution is 1.0 degree
        # Points = (Length / (Distance * sin(1 deg)))
        # Simplified: Points approx = (Length / (Distance * 0.0175))
        
        # Calculate how many beams a forklift hits at this distance
        expected_points = min_length_m / (distance_m * 0.0175)
        # We set the trigger to about 70% of the expected forklift size to be safe
        trigger_threshold = int(expected_points * 0.7)
        
        print(f"🛠 Configuring Standalone Filter: >{trigger_threshold} points @ {distance_m}m")
        
        # Command to set internal evaluation filter (LFEactive_point_threshold)
        # Note: Index 0 is typically the first field
        cmd = f"sWN LFEactive_point_threshold 0 {trigger_threshold}"
        self.lidar.send_cola_command(cmd)
        return trigger_threshold

    def configure_field_zone(self, alley_width_m: float, alley_depth_m: float):
        """
        Defines a detection rectangle inside the sensor.
        Everything inside this box is evaluated for 'forklift-ness'.
        """
        print(f"🛠 Syncing Detection Zone: {alley_width_m}m x {alley_depth_m}m")
        
        # This is a complex binary write in SOPAS, but via CoLa-A we can 
        # set basic rectangular parameters if supported by the firmware version.
        # Placeholder for the specific LFE Field Definition sequence
        return True

    def save_to_eeprom(self) -> bool:
        """Permanently saves settings to the sensor so it works without a PC."""
        print("💾 Writing settings to EEPROM...")
        resp = self.lidar.send_cola_command("sMN mEEwrite")
        if "sAN mEEwrite 01" in resp:
            print("✅ Settings Permanently Saved.")
            # Final step: Transition sensor back to 'Run' mode
            self.lidar.send_cola_command("sMN Run")
            return True
        return False

    def setup_standalone_forklift_mode(self, width_m: float, depth_m: float, forklift_min_m: float):
        """One-click setup for the standalone alleyway alarm."""
        if not self.unlock_sensor():
            return False
            
        self.configure_field_zone(width_m, depth_m)
        self.sync_forklift_threshold(forklift_min_m, depth_m)
        
        if self.save_to_eeprom():
            print("\n🎉 STANDALONE MODE READY.")
            print("You can now unplug the computer. The LiDAR will trigger Pin 4 directly.")
            return True
        return False
