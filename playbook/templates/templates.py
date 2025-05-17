import json
from playbook.models import Playbook, PlaybookSections


def upsert_template(name):
    with open(f"{name}", "r") as f:
        content = f.read()
        template = json.loads(content)

    template_name = template.get("template_name")
    playbook, _ = Playbook.objects.get_or_create(
        name=template_name, description=f"Imported from {name}"
    )

    step_number = 1
    for section in template.get("sections"):
        section_name = section.get("section_name")

        for sec_details in section.get("details"):
            category = sec_details.get("category")
            for question in sec_details.get("questions"):
                PlaybookSections.objects.get_or_create(
                    playbook=playbook,
                    step_number=step_number,
                    section_name=section_name,
                    section_category=category,
                    section_question=question,
                )
        step_number += 1

    return playbook
