"""Exporters for converting structured AeroPostmortem objects into Markdown and JSON."""

from __future__ import annotations

from src.schemas.postmortem import AeroPostmortem


class PostmortemExporter:
    """Serializes AeroPostmortem instances into publication-ready GitHub-Flavored Markdown and JSON."""

    @classmethod
    def to_markdown(cls, postmortem: AeroPostmortem) -> str:
        """Generates a comprehensive, beautifully styled Google SRE Markdown postmortem."""
        pm = postmortem
        impact = pm.impact
        rc = pm.root_cause
        remed = pm.remediation_performed

        # 1. Header & Metadata
        md = [
            f"# {pm.title}",
            "",
            "| Field | Details |",
            "| :--- | :--- |",
            f"| **Postmortem ID** | `{pm.postmortem_id}` |",
            f"| **Incident ID** | `{pm.incident_id}` |",
            f"| **Affected Service** | `{pm.service_name}` |",
            f"| **Severity** | **{pm.severity}** |",
            f"| **Status** | `{pm.status}` |",
            f"| **Published Date** | {pm.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')} |",
            f"| **Total Outage Duration** | {impact.total_downtime_minutes:.1f} minutes |",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            "",
            pm.executive_summary,
            "",
            "---",
            "",
            "## 2. Impact & Blast Radius Assessment",
            "",
            f"- **Primary Microservice:** `{impact.affected_service}`",
            f"- **Outage Severity:** `{impact.severity}`",
            f"- **Total Downtime Duration:** `{impact.total_downtime_minutes:.1f} minutes`",
        ]

        if impact.failed_requests_estimate:
            md.append(f"- **Failed Requests / Dropped Traffic:** {impact.failed_requests_estimate}")

        md.extend([
            f"- **Impacted Customer Workflows:** {impact.impacted_customers_or_flows}",
            "",
            "---",
            "",
            "## 3. Root Cause Analysis",
            "",
            f"### **{rc.title}** (`{rc.category}`)",
            "",
            f"**Trigger Event:** {rc.trigger_event}",
            "",
            "**Causal Chain Breakdown:**",
            rc.causal_chain,
            "",
            "---",
            "",
            "## 4. Five-Whys Deep Causal Hierarchy",
            "",
        ])

        for fw in pm.five_whys:
            md.append(f"{fw.level}. **Why?** {fw.why}")
            md.append(f"   * **Because:** {fw.because}")

        md.extend([
            "",
            "---",
            "",
            "## 5. Chronological Incident Event Timeline",
            "",
            "| Timestamp (UTC) | Milestone Phase | Event Summary | Source Signal |",
            "| :--- | :--- | :--- | :--- |",
        ])

        for m in pm.timeline_milestones:
            ts_str = m.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            md.append(f"| `{ts_str}` | **{m.milestone_type.value}** | {m.title}: {m.description} | `{m.source_signal}` |")

        md.extend([
            "",
            "---",
            "",
            "## 6. Remediation & Recovery Verification",
            "",
            "### Immediate Mitigation Steps Executed:",
        ])

        for i, step in enumerate(remed.immediate_steps):
            md.append(f"{i+1}. {step}")

        if remed.dry_run_command:
            md.extend([
                "",
                "**Dry-Run Verification Command:**",
                f"```bash\n{remed.dry_run_command}\n```",
            ])

        md.extend([
            "",
            f"**Recovery Verification Metric:** `{remed.verification_metric}`",
            "",
            f"**Rollback Contingency Plan:** {remed.rollback_plan}",
            "",
            "---",
            "",
            "## 7. Preventative Action Items",
            "",
            "| ID | Priority | Category | Title & Requirements | Owner | Effort | Verification Criterion |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for act in pm.action_items:
            md.append(
                f"| `{act.id}` | **{act.priority.value}** | `{act.category.value}` | **{act.title}**: {act.description} | "
                f"{act.owner} | `{act.estimated_effort}` | {act.verification} |"
            )

        md.extend([
            "",
            "---",
            "",
            "## 8. Lessons Learned & Blameless Reflections",
            "",
            "### What Went Well:",
        ])
        for item in pm.lessons_learned_what_went_well:
            md.append(f"- {item}")

        md.extend([
            "",
            "### What Went Wrong:",
        ])
        for item in pm.lessons_learned_what_went_wrong:
            md.append(f"- {item}")

        md.extend([
            "",
            "### Where We Got Lucky:",
        ])
        for item in pm.lessons_learned_where_we_got_lucky:
            md.append(f"- {item}")

        md.append("\n<!-- End of AERO Postmortem -->\n")

        return "\n".join(md)

    @classmethod
    def to_json(cls, postmortem: AeroPostmortem, indent: int = 2) -> str:
        """Serializes the postmortem to formatted JSON."""
        return postmortem.model_dump_json(indent=indent)
