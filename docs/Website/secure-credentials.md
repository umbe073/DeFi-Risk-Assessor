# Secure Credentials System

The DeFi Risk Assessment Suite depends on many third-party APIs. To avoid
hard-coding secrets or scattering them across environment files, it ships with
a dedicated **encrypted credentials store** and a desktop **GUI credentials
manager**.

---

## Files and encryption model

The credential system is implemented in:

- `scripts/v2.0/credential_management/gui_credentials.py` – Tkinter-based GUI.  
- `secure_credentials.py` (imported by the GUI) – encryption, decryption and
  file layout.

Credential store files under `DATA_DIR`:

- `creds.meta` – JSON metadata (salt, parameters, possibly key IDs).  
- `creds.enc` – Fernet-encrypted JSON mapping of `{KEY: VALUE}` pairs.

From the GUI docstring:

```1:14:<PROJECT_ROOT>/scripts/v2.0/credential_management/gui_credentials.py
\"\"\"
GUI Credentials Manager (Desktop)
=================================

Provides a simple desktop window to set up/request the master password and
add/edit/delete API keys without using the terminal.

Backed by the encrypted credentials store used by the main script:
- data/creds.meta (JSON with salt)
- data/creds.enc  (Fernet-encrypted JSON of {KEY: VALUE})
\"\"\"
```

Encryption design (conceptual):

- A user-provided **master password** is turned into a key using a KDF and salt
  from `creds.meta`.  
- The derived key is used for symmetric encryption (Fernet or equivalent).  
- The raw master password and derived key are never written to disk.

---

## GUI Credentials Manager

The GUI is launched via:

```bash
python3 scripts/v2.0/credential_management/gui_credentials.py
```

On macOS, the script sets several environment variables to force Tkinter into a
safe “basic” mode and avoid background-app issues:

```16:63:<PROJECT_ROOT>/scripts/v2.0/credential_management/gui_credentials.py
if sys.platform == \"darwin\":
    ...
    os.environ['TK_SILENCE_DEPRECATION'] = '1'
    ...
    os.environ['TK_FORCE_BASIC_MODE'] = '1'
```

The main GUI class `GuiCreds`:

- Creates a centered, foreground window.  
- Imports `derive_key`, `read_store`, `write_store`, `project_paths` from
  `secure_credentials`.  
- Builds a table of known API keys and allows:
  - adding new keys,  
  - editing existing values,  
  - deleting keys no longer in use.

Default key names (excerpt):

```76:115:<PROJECT_ROOT>/scripts/v2.0/credential_management/gui_credentials.py
DEFAULT_API_KEYS = [
    \"ALCHEMY_API_KEY\",
    \"INFURA_API_KEY\",
    \"ETHERSCAN_API_KEY\",
    ...
    \"TRMLABS_API_KEY\",
    \"CHAINABUSE_API_KEY\",
    ...
    \"TWITTER_BEARER_TOKEN\",
    \"TELEGRAM_BOT_TOKEN\",
    \"DISCORD_BOT_TOKEN\",
    ...
]
```

This list covers:

- on-chain and market data APIs,  
- blockchain analytics providers,  
- compliance / sanctions providers,  
- social and news platform credentials.

---

## Integration with the main engine

At runtime, the engine and helper scripts can:

- read the decrypted key/value mapping via `secure_credentials.read_store`, or  
- export selected keys into a `.env` file or environment variables as needed.

The goal is to ensure:

- no secrets are checked into version control,  
- configuration for staging / production / personal environments can differ,  
- rotating or revoking a key is a matter of opening the GUI, updating the value
  and re-running the script.

---

## Operational recommendations

- **Use a strong master password** and share it only with the smallest set of
  trusted operators.  
- **Back up `creds.meta` and `creds.enc`** securely; losing both is equivalent
  to losing all stored credentials.  
- **Rotate keys periodically** and on any suspected compromise; the GUI is
  intended to make this process straightforward.  
- **Avoid environment-only secrets** for long-lived keys; use the encrypted
  store wherever possible.

Together, the encrypted store and GUI credentials manager provide a practical
way to operate a complex, multi-API risk assessment engine without sacrificing
security hygiene.
