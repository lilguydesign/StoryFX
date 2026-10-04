"""Read only public release schema and routing metadata on DB02."""
import subprocess

HOST = ['ssh', '-F', r'C:\Users\lilgu\.ssh\config', 'formafx-db']
QUERIES = {
    'columns': "SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='app_versions' ORDER BY ordinal_position;",
    'story_version': "SELECT row_to_json(v) FROM public.app_versions v WHERE platform='storyfx_agent_android';",
}


def main():
    for name, query in QUERIES.items():
        command = 'sudo docker exec -i formafx-staging-supabase-db psql -X -U postgres -d postgres -P pager=off'
        result = subprocess.run(HOST + [command], input=query, text=True, capture_output=True, check=True)
        print(name + ':\n' + result.stdout)
    command = "sudo sed -n '1,220p' /opt/formafx/supabase-staging/current/volumes/functions/main/index.ts"
    result = subprocess.run(HOST + [command], text=True, capture_output=True, check=True)
    # Router source is public source; do not inspect container environment.
    print('edge_router:\n' + result.stdout)


if __name__ == '__main__':
    main()
