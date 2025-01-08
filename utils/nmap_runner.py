import subprocess
import threading
import json


class NmapRunner:
    def __init__(self, update_result_callback, update_risk_callback=None):
        """
        Initializes the NmapRunner class.
        Args:
            update_result_callback (function): Callback function to handle scan results in real time.
            update_risk_callback (function): Optional callback to handle risk assessment based on scan results.
        """
        self.update_result_callback = update_result_callback
        self.update_risk_callback = update_risk_callback
        self.scan_thread = None
        self.scan_process = None
        self.stop_event = threading.Event()  # Event to signal scan termination

    def build_nmap_command(self, target, port_range, options):
        """
        Constructs the Nmap command based on the provided parameters.
        Args:
            target (str): Target IP or domain.
            port_range (str): Port range as a string (e.g., "20-80").
            options (dict): Dictionary of scan options.
        Returns:
            list: List of command arguments for subprocess.
        """
        base_command = ["nmap"]
        if options.get("scan_type"):
            base_command.append(options["scan_type"].split(": ")[1])
        if port_range:
            base_command.append(f"-p{port_range}")
        if options.get("service_scan"):
            base_command.append("-sV")
        if options.get("os_detection"):
            base_command.append("-O")
        if options.get("aggressive_scan"):
            base_command.append("-A")
        if options.get("verbose"):
            base_command.append("-v")
        if options.get("no_ping"):
            base_command.append("-Pn")
        if target:
            base_command.append(target)
        else:
            raise ValueError("Target cannot be empty.")
        return base_command

    def run_scan(self, command):
        """
        Executes the Nmap scan and streams the output in real time.
        Args:
            command (list): List of command arguments to execute.
        """
        try:
            self.update_result_callback(f"Starting scan: {' '.join(command)}")
            self.scan_process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for line in self.scan_process.stdout:
                if self.stop_event.is_set():
                    self.terminate_scan_process()
                    self.update_result_callback("Scan stopped by user.")
                    return
                self.update_result_callback(line.strip())
            self.scan_process.wait()
            if not self.stop_event.is_set():
                self.update_result_callback("Scan completed successfully.")
        except Exception as e:
            self.update_result_callback(f"Error: {str(e)}")
        finally:
            self.cleanup_process()

    def terminate_scan_process(self):
        """Forcefully terminate the scan subprocess."""
        if self.scan_process:
            try:
                self.scan_process.terminate()  # Attempt graceful termination
                self.scan_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.scan_process.kill()  # Force kill if not terminated
            finally:
                self.scan_process = None
                self.stop_event.clear()

    def cleanup_process(self):
        """Clean up the scan process and reset the stop event."""
        self.scan_process = None
        self.stop_event.clear()

    def start_scan(self, target, port_range, options):
        """
        Starts a new scan in a separate thread.
        Args:
            target (str): Target IP or domain.
            port_range (str): Port range as a string (e.g., "20-80").
            options (dict): Dictionary of scan options.
        """
        if self.scan_thread and self.scan_thread.is_alive():
            self.update_result_callback("A scan is already in progress. Please wait.")
            return
        command = self.build_nmap_command(target, port_range, options)
        self.stop_event.clear()
        self.scan_thread = threading.Thread(target=self.run_scan, args=(command,), daemon=True)
        self.scan_thread.start()

    def stop_scan(self):
        """
        Stops the currently running scan.
        """
        if self.scan_process and self.scan_process.poll() is None:
            self.stop_event.set()
            self.terminate_scan_process()
        else:
            self.update_result_callback("No active scan to stop.")
