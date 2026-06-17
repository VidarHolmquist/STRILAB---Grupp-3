# Skill: `/initialise`

> Initialise the repository, configure the virtual environment, install dependencies, and verify the local setup.

## Steps

1. **Verify Python Version**
   - Run:
     ```bash
     python --version
     ```
   - Target version must be **Python 3.9+**.
   - If Python is not installed or the version is less than 3.9, **stop and report** to the user.

2. **Create Virtual Environment**
   - Check if a `.venv` directory exists in the project root.
   - If not, create it by running:
     ```bash
     python -m venv .venv
     ```

3. **Activate Virtual Environment**
   - Activate the `.venv` according to the current shell/OS:
     - **Windows (PowerShell):**
       ```powershell
       .venv\Scripts\Activate.ps1
       ```
     - **Windows (CMD):**
       ```cmd
       .venv\Scripts\activate.bat
       ```
     - **Linux / macOS (Bash/Zsh):**
       ```bash
       source .venv/bin/activate
       ```

4. **Upgrade Pip and Install Dependencies**
   - Ensure pip is upgraded:
     ```bash
     python -m pip install --upgrade pip
     ```
   - Install all required Python packages from the root `requirements.txt`:
     ```bash
     pip install -r requirements.txt
     ```
     > [!NOTE]
     > The `requirements.txt` file specifies CPU-only options for `torch` and `torchvision` (`--extra-index-url https://download.pytorch.org/whl/cpu`) to keep the footprint lightweight.

5. **Verify the Installation**
   - Ensure environment variable `PYTHONPATH` includes the project root directory:
     - **Windows (PowerShell):**
       ```powershell
       $env:PYTHONPATH="."
       ```
     - **Windows (CMD):**
       ```cmd
       set PYTHONPATH=.
       ```
     - **Linux / macOS (Bash/Zsh):**
       ```bash
       export PYTHONPATH=.
       ```
   - Run the retrieval metrics check to verify all imports and configurations work properly:
     ```bash
     python metrics/evaluate_rag.py
     ```
   - If successful, you will see a printout of retrieval metrics (Hit Rate, MRR, Recall) and the test will complete.

6. **Run Streamlit Frontend**
   - Launch the local user interface:
     ```bash
     streamlit run frontend/app.py
     ```

## Abort Conditions

- **Python missing or outdated:** If Python 3.9+ is not available.
- **Dependency installation failure:** If `pip install -r requirements.txt` fails (e.g., due to package conflict or network issues).
- **Verification failure:** If running `python metrics/evaluate_rag.py` throws ImportError, database connection issues, or other exceptions.
