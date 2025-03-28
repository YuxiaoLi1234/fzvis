# :computer: Installation

## :one: Prerequisites

Please make sure the following software, library, tools, and packages are installed for the FZ-VIS project. **We strongly recommend using a Node version manager like [nvm](https://github.com/nvm-sh/nvm) to install Node.js and npm.**

### Dependencies

1. [libpressio](https://github.com/robertu94/libpressio)
2. [Node.js (version >= 18.12.0)](https://nodejs.org/)
3. [npm (version >= 8.19.0)](https://www.npmjs.com/)
4. [Python 3 (version >= 3.9.0)](https://www.python.org/downloads/)
5. [Anaconda/Miniconda (optional)](https://www.anaconda.com/download/)

:warning: For `libpressio`, please make sure Python bindings are also installed.

### (Optional) Setting up a Python virtual environment

We suggest using a virtual environment for setting up and running the web services. 

- If `conda` is installed, you can create a virtual environment named 'fzenv' using the following command:
    ```sh
    conda create -n fzenv
    ```
    - You can always view all created virtual environments in the system using `conda info -e`.  
    - **Activation**: use command `conda activate fzenv`.  
    - **Deactivation**: use `conda deactivate`. 

- Otherwise, you can use the `venv` package from Python to create a virtual environment, and this will create a `fzenv` folder under the directory. 
    ```sh
    python -m venv fzenv
    ```
    - **Activation**: Use `fzenv\Scripts\activate.bat` for Command Prompt and `fzenv\Scripts\Activate.ps` for PowerShell on a Windows system, and use `source fzenv/bin/activate` on a Linux/macOS system.  
    - **Deactivation**: Just enter `deactivate` in the terminal. It works the same on all operating systems.

- :warning: Make sure the virtual environment is active by checking for `(fzenv)` at the beginning of the terminal prompt.


## :two: Install Modules/Packages

To install required Node.js modules, use `npm ci` command for a clean installation. 

To install required Python packages, use `pip install -r requirements.txt` command.

## :three: Test and Run

Enter your desired IP address and port in `config.json`.

To run the front-end service, use the command `npm run serve`.

To run the back-end service, use the following command. 
```sh
python3 ./src/components/main.py
```
