# IoTGuard - Smart Home Security

![IoTGuard Logo](https://via.placeholder.com/150.png?text=IoTGuard) IoTGuard is a smart home security application designed to analyze IoT commands for potential security risks using the Gemini API. It provides a user-friendly interface to manage IoT devices, enforce security rules, and ensure safe command execution. Built with Python and PySide6, IoTGuard is ideal for securing smart home environments by identifying risks and suggesting safer alternatives.

## Features

-   **Command Risk Analysis**: Analyzes IoT commands (e.g., `unlock door`, `play music on speakers`) for security risks using the Gemini API.
-   **Risk Assessment**: Displays risk levels (None, Low, Medium, High, Critical), explanations, suggestions, and safe command alternatives.
-   **User Management**:
    -   Custom user creation with user-defined names and PINs.
    -   Device permissions for each user, allowing fine-grained control over which devices a user can manage.
    -   Master user (`master_user`) with full administrative privileges.
-   **Device Management**:
    -   Tracks device status (e.g., `door1 - locked`, `speakers - on`).
    -   Supports multiple devices (`door1`, `camera1`, `speakers`) with dynamic state updates.
-   **Security Rules**: Apply predefined rules (e.g., "Always require authentication for door commands") to block or modify risky commands.
-   **Command History**: Stores a timestamped history of commands with risk levels and results, searchable and persistent across sessions.
-   **Responsive GUI**:
    -   Built with PySide6 for a modern, user-friendly interface.
    -   Supports light and dark themes with a toggle button.
    -   System tray integration for minimizing and restoring the app.
-   **Error Handling**:
    -   Robust error handling for API calls, user input, and database operations.
    -   Detailed logging to `resources/iotguard_log.txt` for debugging.
-   **Performance**:
    -   Command caching to reduce redundant API calls.
    -   Threaded API calls to keep the GUI responsive.
-   **Educational Features**:
    -   "Learn More" link with detailed risk information and security tips.
    -   Visual risk indicators (e.g., ⚠️ for High risk).
-   **Premium Features (Simulated)**:
    -   Real-time alerts via system tray notifications for risky commands.
    -   "Real-Time Alerts Enabled (Premium)" label for simulated premium functionality.

## Prerequisites

-   **Python 3.8+**: Ensure Python is installed on your system.
-   **Git**: For cloning the repository.
-   **Google Gemini API Key**: Required for command analysis.

## Setup Instructions

1.  **Clone the Repository**:

    ```bash
    git clone [https://github.com/DarthAether/IoTGuard.git](https://github.com/DarthAether/IoTGuard.git)
    cd IoTGuard
    ```

2.  **Create a Virtual Environment**:

    ```bash
    python -m venv myenv
    source myenv/bin/activate  # On Windows: myenv\Scripts\activate
    ```

3.  **Install Dependencies**:

    Install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables**:

    Create a `.env` file in the project root and add your Gemini API key:

    ```text
    GOOGLE_API_KEY=your_api_key_here
    ```

    You can obtain a Gemini API key from the Google Cloud Console.

5.  **Run the Application**:

    ```bash
    python app/main.py
    ```

## Usage

1.  **Log In**:

    Use the default `master_user` credentials:

    -   User ID: `master_user`
    -   PIN: `1234`

    You can create additional users via the "Manage Users" dialog.

2.  **Analyze a Command**:

    -   Enter a User ID and PIN.
    -   Select a device (e.g., `door1`, `speakers`).
    -   Input an IoT command (e.g., `unlock door`).
    -   Click "Check Risks" to analyze the command for security risks.

3.  **Manage Users**:

    -   Click "Manage Users" (only accessible to `master_user`).
    -   Add a new user with a custom User ID, PIN, and device permissions.
    -   Update or delete existing users as needed.

4.  **View Command History**:

    -   The "Command History" section shows a timestamped log of all commands, including risk levels and results.
    -   Use the search bar to filter history entries.

5.  **Apply Security Rules**:

    -   Select a security rule from the dropdown (e.g., "Always require authentication for door commands") to enforce additional safety checks.

## Project Structure

```text
IoTGuard/
├── app/
│   ├── gui.py              # Main GUI implementation
│   ├── main.py             # Entry point for the application
│   ├── user_management.py  # User management dialog
│   ├── theme.py            # Theme management (light/dark mode)
│   └── animations.py       # GUI animations
├── backend/
│   ├── database.py         # SQLite database management
│   ├── iot_backend.py      # IoT device management and command execution
│   └── gemini_worker.py    # Gemini API integration
├── resources/
│   ├── history.json        # Persistent command history
│   ├── users.db            # SQLite database for user data
│   └── iotguard_log.txt    # Application logs
├── utils/
│   ├── config.py           # Configuration and environment variable loading
│   └── helpers.py          # Utility functions
├── .env                    # Environment variables (not tracked)
├── .gitignore              # Git ignore file
├── requirements.txt        # Project dependencies
├── LICENSE                 # MIT License
└── README.md               # Project documentation

Markdown

# IoTGuard - Smart Home Security

![IoTGuard Logo](https://via.placeholder.com/150.png?text=IoTGuard) IoTGuard is a smart home security application designed to analyze IoT commands for potential security risks using the Gemini API. It provides a user-friendly interface to manage IoT devices, enforce security rules, and ensure safe command execution. Built with Python and PySide6, IoTGuard is ideal for securing smart home environments by identifying risks and suggesting safer alternatives.

## Features

-   **Command Risk Analysis**: Analyzes IoT commands (e.g., `unlock door`, `play music on speakers`) for security risks using the Gemini API.
-   **Risk Assessment**: Displays risk levels (None, Low, Medium, High, Critical), explanations, suggestions, and safe command alternatives.
-   **User Management**:
    -   Custom user creation with user-defined names and PINs.
    -   Device permissions for each user, allowing fine-grained control over which devices a user can manage.
    -   Master user (`master_user`) with full administrative privileges.
-   **Device Management**:
    -   Tracks device status (e.g., `door1 - locked`, `speakers - on`).
    -   Supports multiple devices (`door1`, `camera1`, `speakers`) with dynamic state updates.
-   **Security Rules**: Apply predefined rules (e.g., "Always require authentication for door commands") to block or modify risky commands.
-   **Command History**: Stores a timestamped history of commands with risk levels and results, searchable and persistent across sessions.
-   **Responsive GUI**:
    -   Built with PySide6 for a modern, user-friendly interface.
    -   Supports light and dark themes with a toggle button.
    -   System tray integration for minimizing and restoring the app.
-   **Error Handling**:
    -   Robust error handling for API calls, user input, and database operations.
    -   Detailed logging to `resources/iotguard_log.txt` for debugging.
-   **Performance**:
    -   Command caching to reduce redundant API calls.
    -   Threaded API calls to keep the GUI responsive.
-   **Educational Features**:
    -   "Learn More" link with detailed risk information and security tips.
    -   Visual risk indicators (e.g., ⚠️ for High risk).
-   **Premium Features (Simulated)**:
    -   Real-time alerts via system tray notifications for risky commands.
    -   "Real-Time Alerts Enabled (Premium)" label for simulated premium functionality.

## Prerequisites

-   **Python 3.8+**: Ensure Python is installed on your system.
-   **Git**: For cloning the repository.
-   **Google Gemini API Key**: Required for command analysis.

## Setup Instructions

1.  **Clone the Repository**:

    ```bash
    git clone [https://github.com/DarthAether/IoTGuard.git](https://github.com/DarthAether/IoTGuard.git)
    cd IoTGuard
    ```

2.  **Create a Virtual Environment**:

    ```bash
    python -m venv myenv
    source myenv/bin/activate  # On Windows: myenv\Scripts\activate
    ```

3.  **Install Dependencies**:

    Install the required Python packages:

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Up Environment Variables**:

    Create a `.env` file in the project root and add your Gemini API key:

    ```text
    GOOGLE_API_KEY=your_api_key_here
    ```

    You can obtain a Gemini API key from the Google Cloud Console.

5.  **Run the Application**:

    ```bash
    python app/main.py
    ```

## Usage

1.  **Log In**:

    Use the default `master_user` credentials:

    -   User ID: `master_user`
    -   PIN: `1234`

    You can create additional users via the "Manage Users" dialog.

2.  **Analyze a Command**:

    -   Enter a User ID and PIN.
    -   Select a device (e.g., `door1`, `speakers`).
    -   Input an IoT command (e.g., `unlock door`).
    -   Click "Check Risks" to analyze the command for security risks.

3.  **Manage Users**:

    -   Click "Manage Users" (only accessible to `master_user`).
    -   Add a new user with a custom User ID, PIN, and device permissions.
    -   Update or delete existing users as needed.

4.  **View Command History**:

    -   The "Command History" section shows a timestamped log of all commands, including risk levels and results.
    -   Use the search bar to filter history entries.

5.  **Apply Security Rules**:

    -   Select a security rule from the dropdown (e.g., "Always require authentication for door commands") to enforce additional safety checks.

## Project Structure

```text
IoTGuard/
├── app/
│   ├── gui.py              # Main GUI implementation
│   ├── main.py             # Entry point for the application
│   ├── user_management.py  # User management dialog
│   ├── theme.py            # Theme management (light/dark mode)
│   └── animations.py       # GUI animations
├── backend/
│   ├── database.py         # SQLite database management
│   ├── iot_backend.py      # IoT device management and command execution
│   └── gemini_worker.py    # Gemini API integration
├── resources/
│   ├── history.json        # Persistent command history
│   ├── users.db            # SQLite database for user data
│   └── iotguard_log.txt    # Application logs
├── utils/
│   ├── config.py           # Configuration and environment variable loading
│   └── helpers.py          # Utility functions
├── .env                    # Environment variables (not tracked)
├── .gitignore              # Git ignore file
├── requirements.txt        # Project dependencies
├── LICENSE                 # MIT License
└── README.md               # Project documentation
Contributing
Contributions are welcome! To contribute:

Fork the repository.
Create a new branch (git checkout -b feature/your-feature).
Make your changes and commit them (git commit -m "Add your feature").
Push to your branch (git push origin feature/your-feature).
Open a Pull Request on GitHub.
Please ensure your code follows the existing style and includes appropriate logging.

License
This project is licensed under the MIT License. See the LICENSE file for details.

Acknowledgments
Built with PySide6 for the GUI.
Uses the Google Gemini API for command risk analysis.
Developed with assistance from Grok (xAI).
Contact
For questions or support, contact DarthAether on GitHub.