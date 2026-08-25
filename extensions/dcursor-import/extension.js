const vscode = require("vscode");
const { execFile, execFileSync } = require("child_process");
const { promisify } = require("util");

const execFileAsync = promisify(execFile);

const IMPORT_SCRIPT = "/usr/share/dcursor/bin/dcursor-import-cursor-conversations.py";

function getImportScript() {
  return IMPORT_SCRIPT;
}

function isProcessRunning(name) {
  try {
    execFileSync("pgrep", ["-x", name], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

async function confirmImportIfAppsRunning() {
  const cursorRunning = isProcessRunning("cursor");
  const dcursorRunning = isProcessRunning("dcursor");
  if (!cursorRunning && !dcursorRunning) {
    return true;
  }

  const apps = [
    cursorRunning ? "Cursor" : null,
    dcursorRunning ? "dCursor" : null,
  ]
    .filter(Boolean)
    .join(" and ");

  const choice = await vscode.window.showWarningMessage(
    `${apps} appears to be running. Import is read-only on Cursor, but live databases may be inconsistent. Close both apps for best results.`,
    { modal: true },
    "Import anyway",
    "Cancel",
  );
  return choice === "Import anyway";
}

async function runImport(dryRun = false) {
  const script = getImportScript();

  const choice = dryRun
    ? "Preview"
    : await vscode.window.showWarningMessage(
        "Import chat history from main Cursor into dCursor? Main Cursor is read-only and will not be modified.",
        { modal: true },
        "Import",
        "Preview",
        "Cancel",
      );

  if (!choice || choice === "Cancel") {
    return;
  }

  const preview = choice === "Preview" || dryRun;

  if (!preview && !(await confirmImportIfAppsRunning())) {
    return;
  }

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: preview
        ? "Previewing Cursor conversation import..."
        : "Importing conversations from Cursor...",
      cancellable: false,
    },
    async () => {
      const args = [script];
      if (preview) {
        args.push("--dry-run");
      }

      const { stdout, stderr } = await execFileAsync("python3", args);

      const output = [stdout, stderr].filter(Boolean).join("\n").trim();
      if (output) {
        const doc = await vscode.workspace.openTextDocument({
          content: output,
          language: "log",
        });
        await vscode.window.showTextDocument(doc, { preview: true });
      }

      if (!preview) {
        const restart = await vscode.window.showInformationMessage(
          "Import complete. Restart dCursor to see imported conversations.",
          "Reload Window",
        );
        if (restart === "Reload Window") {
          await vscode.commands.executeCommand("workbench.action.reloadWindow");
        }
      } else {
        vscode.window.showInformationMessage(
          "Dry-run complete. Run again without Preview to apply.",
        );
      }
    },
  );
}

function activate(context) {
  context.subscriptions.push(
    vscode.commands.registerCommand("dcursor.importFromCursor", () =>
      runImport(false),
    ),
  );

  const status = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    50,
  );
  status.command = "dcursor.importFromCursor";
  status.text = "$(cloud-download) Import from Cursor";
  status.tooltip =
    "Copy conversations from main Cursor into dCursor (read-only, never modifies Cursor)";
  status.show();
  context.subscriptions.push(status);
}

function deactivate() {}

module.exports = { activate, deactivate };
