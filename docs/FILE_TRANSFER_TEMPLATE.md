# File Transfer Strategy Template

## Overview

This template outlines the standard method for transferring files (PDFs, Images, Videos) via the Off-Grid Agent to SMS users. Due to MMS limitations (size caps, carrier blocking), we use a "Cloud Link + Fallback" strategy.

## The Strategy

1. **Attempt Cloud Upload (Primary)**:
   - Upload the file to a temporary hosting provider (`tmpfiles.org` is preferred for transient data).
   - Generate a direct download link.
   - Send this link in the SMS body.

2. **Attachment Fallback**:
   - Attempt to attach the file directly to the email (MMS).
   - This works for small images (<1MB) but often fails for PDFs or videos.
   - We do BOTH: Send the link (reliable) AND the attachment (convenient if it works).

3. **Link Obfuscation (Anti-Spam)**:
   - Carriers (T-Mobile, Verizon) often block raw URLs.
   - Send multiple variants of the link in separate emails:
     - Broken Link: `example . com / file` (User must fix)
     - HTML Link: `<a href="...">Click Here</a>` (If supported)
     - Raw Link: Standard URL.

## Implementation (Python)

We use the `CloudUploader` class (`recipe.cloud_uploader`) which implements a priority chain: `tmpfiles` -> `catbox` -> `transfer.sh` -> `0x0`.

### Code Snippet

```python
from recipe.cloud_uploader import CloudUploader

# 1. Initialize Uploader (Defaults to 'tmpfiles' generic provider)
# You can force a specific provider by overriding settings if needed.
uploader = CloudUploader(_SETTINGS) 

# 2. Upload File
# Returns a direct URL (e.g. https://tmpfiles.org/dl/...) or None if all failed.
file_path = "path/to/file.pdf"
public_link = uploader.upload_file(file_path)

# 3. Construct Message
response_text = "Here is your file:"
if public_link:
    # FORCE HTTPS
    if not public_link.startswith("http"):
        public_link = "https://" + public_link
        
    response_text += f"\n\n[ DOWNLOAD LINK ]\n{public_link}"
else:
    response_text += "\n(Upload failed, attempting direct attachment only)"

# 4. Send (Assuming standard send_sms_reply function)
# attachment_path arg ensures MMS attempt
send_sms_reply(user_email, response_text, attachment_path=file_path)
```

## Preferred Provider: tmpfiles.org

- **Why**: No account required, 60-minute retention (perfect for ephemeral agent responses), fast, simple API.
- **API**: POST to `https://tmpfiles.org/api/v1/upload`
- **Result**: Must convert display URL to download URL by adding `/dl/`.

## Fallbacks

- **Transfer.sh**: 14-day retention. Good backup.
- **Catbox.moe**: Permanent. Use sparingly.
- **Mega.nz**: Requires auth. Good for large persistent files.
