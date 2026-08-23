# Security

This project handles sensitive student application materials. Do not commit:

- Real resumes, transcripts, recommendation material, or contact records
- `.env` files or API keys
- Generated application materials for real users
- Full copied pages from advisor websites when a short source summary is enough
- Raw mailbox exports or pasted email bodies from real users

The app never sends contact emails automatically. Users must review and send all generated materials themselves.

Email signal import in the MVP is pasted-text based and read-only. Candidates must be approved by the user before they update the local tracker, archive, or outcome. Do not sync raw email bodies to external dashboards.
