"""Human-in-the-loop exception review (Task 8).

Exceptions raised by matching (variance / missing-PO / duplicate) are queued for
a human approver. Approving posts the Payment Journal and resumes the workflow;
rejecting closes the invoice. Every decision is written to the audit trail.
"""
