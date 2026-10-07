# Support Ticket Dashboard

## Question

We need to display a list of support tickets for agents.

Each ticket shows:

- ID
- Customer name
- Subject
- Status
- Priority
- Created date

We expect thousands of tickets, so we need pagination.

## My answer

I would expose a paginated endpoint such as:

```http
GET /tickets?status=open&sort=created_at&limit=50&cursor=...
```

The list endpoint should return only the fields needed for the dashboard: ticket ID, customer name, subject, status, priority, and created date. It should not load comments, attachments, or full ticket details because those belong on the ticket detail endpoint.

For a small dataset, offset pagination is simple:

```http
GET /tickets?limit=50&offset=100
```

However, for a large or frequently changing ticket list, I would prefer cursor-based pagination. Offset pagination becomes slower at deep pages and can cause duplicate or missing records when tickets are created while an agent is paging through the list.

I would use a deterministic sort order:

```sql
ORDER BY created_at DESC, id DESC
```

The cursor would contain the last returned ticket's `created_at` and `id`. The next request fetches tickets after that position in the same sort order.

For the default listing, I would create an index that matches sorting:

```sql
CREATE INDEX idx_tickets_created_id
ON tickets (created_at DESC, id DESC);
```

If filtering by status is common, I would consider a composite index:

```sql
CREATE INDEX idx_tickets_status_created_id
ON tickets (status, created_at DESC, id DESC);
```

I would allow only a whitelisted set of filter and sort fields, rather than letting clients pass arbitrary database columns. The response should contain the ticket items and a `next_cursor` when another page exists.

Example response:

```json
{
  "items": [
    {
      "id": "ticket_123",
      "customerName": "Jane Doe",
      "subject": "Cannot log in",
      "status": "open",
      "priority": "high",
      "createdAt": "2025-12-01T10:30:00Z"
    }
  ],
  "nextCursor": "base64-encoded-created-at-and-id"
}
```

## Topics

REST API, pagination, cursor pagination, offset pagination, PostgreSQL, database indexing, API design, scalability

## Source

Xnip2025-12-01_18-12-27.jpg