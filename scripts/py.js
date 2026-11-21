// Runs the Python side of the project from npm, on Windows, macOS or Linux.
//   node scripts/py.js setup   create .venv if needed and install requirements.txt
//   node scripts/py.js dev     start the server with reload (PORT env var, default 8000)
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const venvPython = process.platform === "win32"
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: "inherit" });
  if (result.error) return false;
  if (result.status !== 0) process.exit(result.status ?? 1);
  return true;
}

function setup() {
  if (!fs.existsSync(venvPython)) {
    const made = ["python", "python3", "py"].some((python) => run(python, ["-m", "venv", ".venv"]));
    if (!made) {
      console.error("Python 3.10 or newer is required but was not found on PATH.");
      process.exit(1);
    }
  }
  run(venvPython, ["-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-r", "requirements.txt"]);
}

function dev() {
  if (!fs.existsSync(venvPython)) setup();
  const port = process.env.PORT || "8000";
  console.log(`Referral notes: http://localhost:${port}`);
  run(venvPython, ["-m", "uvicorn", "app.main:app", "--reload", "--port", port]);
}

function buildStatic() {
  if (!fs.existsSync(venvPython)) setup();
  run(venvPython, ["scripts/build_static.py"]);
}

const task = { setup, dev, static: buildStatic }[process.argv[2]];
if (!task) {
  console.error("Usage: node scripts/py.js <setup|dev|static>");
  process.exit(1);
}
task();
