import io
import json
import csv

def csv_to_targets_json(csv_file):
	reader = csv.DictReader(csv_file)
	targets = []
	for row in reader:
		project_id_raw = row.get("Gitlab Project ID", "") or ""
		branch_raw = row.get("Branch", "") or ""
		exclusion_globs = row.get("exclusionGlobs", "")
		files = row.get("Files", "")

		project_ids = [pid.strip() for pid in project_id_raw.replace('\n', ',').split(',') if pid.strip()]
		branches = [b.strip() for b in branch_raw.replace('\n', ',').split(',') if b.strip()]
		if len(branches) < len(project_ids):
			branches += ['master'] * (len(project_ids) - len(branches))
		for pid, branch in zip(project_ids, branches):
			targets.append({
				"orgId": "******",
				"integrationId": "******",
				"target": {
					"id": int(pid) if pid.isdigit() else pid,
					"branch": branch,
					"exclusionGlobs": exclusion_globs,
					"files": files
				}
			})
	return {"targets": targets}

def test_csv_to_targets_json():
	with open("/Users/brookecastleberry/Desktop/TEST_Copilot.csv", newline='', encoding='utf-8') as csv_file:
		# Skip the first row if it is not a header
		lines = csv_file.readlines()
		if lines[0].strip().startswith("Table 1"):
			lines = lines[1:]
		csv_file = io.StringIO(''.join(lines))
		result = csv_to_targets_json(csv_file)
		with open("/Users/brookecastleberry/Desktop/assets-import-tool/targets.json", "w", encoding="utf-8") as out_json:
			json.dump(result, out_json, indent=2)
		print("Results written to targets.json")

if __name__ == "__main__":
	test_csv_to_targets_json()
