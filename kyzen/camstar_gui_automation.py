import tkinter as tk
from tkinter import messagebox, scrolledtext
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading

# Global browser instance
driver = None

def run_automation(items):
    global driver
    try:
        # Launch browser if not already running
        if driver is None or not driver.service.is_connectable():
            driver = webdriver.Chrome()
            driver.maximize_window()

        wait = WebDriverWait(driver, 120)  # Allow time for manual login
        driver.get("https://bhvnprd.ad.onsemi.com/CamstarPortal/Main.aspx")

        # Wait for user to manually log in
        wait.until(EC.presence_of_element_located((By.ID, "ctl00_NavigationMenu_NavigationMenu")))

        for item in items:
            if len(item) != 8:
                print(f"Skipping invalid Carrier ID: {item}")
                continue

            driver.get("https://bhvnprd.ad.onsemi.com/CamstarPortal/Main.aspx")
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#ctl00_NavigationMenu_NavigationMenu > ul > li:nth-of-type(6) > a'))).click()
            wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Carrier Set Status"))).click()

            # Switch to iframe
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframe = driver.find_elements(By.TAG_NAME, "iframe")[0]
            driver.switch_to.frame(iframe)

            # Enter Carrier ID
            carrier_input = wait.until(EC.presence_of_element_located((By.ID, "ctl00_WebPartManager_BlankWP_Resource_Edit")))
            carrier_input.clear()
            carrier_input.send_keys(item)
            carrier_input.send_keys(Keys.ENTER)

            # Wait for page to refresh and iframe to reload
            WebDriverWait(driver, 10).until(EC.staleness_of(carrier_input))
            driver.switch_to.default_content()
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframe = driver.find_elements(By.TAG_NAME, "iframe")[0]
            driver.switch_to.frame(iframe)

            # Re-locate and click Status C_DOWN
            wait.until(EC.element_to_be_clickable((By.ID, "ctl00_WebPartManager_BlankWP_ResourceStatus_Edit"))).click()
            wait.until(EC.element_to_be_clickable((By.ID, "ctl00_WebPartManager_BlankWP_ResourceStatus_Imbt"))).click()
            wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_WebPartManager_BlankWP_ResourceStatus_Panl"]/div[3]/ul/li[3]'))).click()

            # Select Status Reason
            wait.until(EC.element_to_be_clickable((By.ID, "ctl00_WebPartManager_BlankWP_ResourceStatusReason_Imbt"))).click()
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#ctl00_WebPartManager_BlankWP_ResourceStatusReason_Panl li.jstree-last"))).click()

            # Submit
            wait.until(EC.element_to_be_clickable((By.ID, "ctl00_WebPartManager_ButtonsBar_Set_Status"))).click()

            driver.switch_to.default_content()

        messagebox.showinfo("Success", "Automation completed successfully.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

def start_automation():
    items = items_text.get("1.0", tk.END).strip().splitlines()

    if not items:
        messagebox.showwarning("Input Error", "Please enter at least one item.")
        return

    threading.Thread(target=run_automation, args=(items,), daemon=True).start()

# GUI setup
root = tk.Tk()
root.title("Camstar Automation")

tk.Label(root, text="Items (one per line):").grid(row=0, column=0, sticky="ne")
items_text = scrolledtext.ScrolledText(root, width=40, height=10)
items_text.grid(row=0, column=1)

submit_button = tk.Button(root, text="Submit", command=start_automation)
submit_button.grid(row=1, column=1, pady=10)

root.mainloop()
