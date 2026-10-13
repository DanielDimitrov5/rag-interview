# Ticket attachments

## Question

Customers attach screenshots when creating tickets. Agents need to view and download these files. Files can be images, PDFs, or documents up to 10MB each.

## My answer

I would store the files in object storage such as S3 rather than in the application server or relational database. The ticket service should keep attachment metadata in Postgres, such as ticket ID, object key, original filename, size, detected content type, upload status, and uploader.

For uploads, I would use a direct-to-storage flow with a presigned URL. The backend authenticates the user, validates allowed file types and the 10MB size limit, generates a short-lived upload URL for a specific object key, and returns it. The client uploads the file directly to object storage, which keeps binary traffic away from the application servers. Presigned URLs provide time-limited access without exposing storage credentials. [web:569][web:572]

I would not trust only the file extension or browser-supplied content type. After upload, I would validate the real file type and run malware scanning before the file becomes available to agents, because OWASP recommends allowlisting file types, validating content, and scanning uploaded files. [web:570][web:573][web:575]

For serving files, agents should request access through the backend, which checks ticket authorization and then returns a short-lived presigned download URL or streams the file through a controlled endpoint. That keeps authorization in the application layer while object storage efficiently handles download traffic. [web:569][web:581]

Because files are limited to 10MB, a simple single-request upload is enough for now. The core design principle is to keep metadata in Postgres and binary content in object storage.

## Topics

object storage, S3, presigned URLs, file uploads, security, malware scanning, PostgreSQL, metadata, attachments

## Source

manual-note