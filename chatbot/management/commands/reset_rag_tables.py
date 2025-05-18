# chatbot/management/commands/reset_rag_tables.py
import logging
import psycopg2
import time
import sys
import signal
import os
from django.core.management.base import BaseCommand
from django.core import management
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reset the RAG database tables to fix embedding dimension issues"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Connection timeout in seconds (default: 30)",
        )
        parser.add_argument(
            "--force", action="store_true", help="Force drop tables even if locks exist"
        )
        parser.add_argument(
            "--hard-timeout",
            type=int,
            default=int(os.getenv("RAG_RESET_HARD_TIMEOUT", 120)),
            help="Hard timeout for entire command in seconds (default from RAG_RESET_HARD_TIMEOUT env var or 120)",
        )
        parser.add_argument(
            "--local",
            action="store_true",
            help="Force use of local database settings instead of cloud",
        )
        parser.add_argument(
            "--debug", action="store_true", help="Enable extra debug output"
        )
        parser.add_argument(
            "--install-deps",
            action="store_true",
            help="Automatically install missing dependencies like spaCy models",
        )

    def handle(self, *args, **kwargs):
        timeout = kwargs.get("timeout", 30)
        force = kwargs.get("force", False)
        hard_timeout = kwargs.get(
            "hard_timeout", int(os.getenv("RAG_RESET_HARD_TIMEOUT", 120))
        )
        use_local = kwargs.get("local", False)
        debug = kwargs.get("debug", False)
        install_deps = kwargs.get("install_deps", False)

        # Check for dependencies before proceeding
        if install_deps:
            self.stdout.write(
                self.style.NOTICE("Checking for required dependencies...")
            )
            self._ensure_dependencies()

        # Set hard timeout handler
        def timeout_handler(signum, frame):
            self.stderr.write(
                self.style.ERROR(
                    f"Hard timeout reached after {hard_timeout} seconds. Command aborted."
                )
            )
            sys.exit(1)

        # Register the timeout handler
        signal.signal(signal.SIGABR, timeout_handler)
        signal.alarm(hard_timeout)

        conn = None
        try:
            self.stdout.write(
                self.style.NOTICE("Connecting to database to reset RAG tables...")
            )

            # Get database configuration based on settings
            if use_local:
                db_config = {
                    "dbname": settings.DATABASES["default"].get(
                        "NAME", "mindcare_local"
                    ),
                    "user": settings.DATABASES["default"].get("USER", "postgres"),
                    "password": settings.DATABASES["default"].get(
                        "PASSWORD", "mindcare"
                    ),
                    "host": "localhost",
                    "port": "5432",
                    "connect_timeout": timeout,
                    "application_name": "reset_rag_tables",
                }
                self.stdout.write("Using LOCAL database configuration")
            else:
                db_config = {
                    "dbname": settings.DATABASES["default"]["NAME"],
                    "user": settings.DATABASES["default"]["USER"],
                    "password": settings.DATABASES["default"]["PASSWORD"],
                    "host": settings.DATABASES["default"]["HOST"],
                    "port": settings.DATABASES["default"]["PORT"],
                    "connect_timeout": timeout,
                    "application_name": "reset_rag_tables",
                }

                # Add SSL options for Neon if needed
                if "neon.tech" in db_config["host"]:
                    db_config["sslmode"] = "require"
                    self.stdout.write("Using SSL mode for Neon database")

            self.stdout.write(
                f"Connecting to {db_config['host']}:{db_config['port']}..."
            )
            if debug:
                self.stdout.write(
                    f"Connection string: dbname='{db_config['dbname']}' user='{db_config['user']}' host='{db_config['host']}' port='{db_config['port']}' connect_timeout={db_config['connect_timeout']}"
                )

            # Try to establish connection with clear timeout
            connection_start = time.time()
            conn = psycopg2.connect(**db_config)
            connection_time = time.time() - connection_start
            self.stdout.write(
                self.style.SUCCESS(
                    f"Database connection established in {connection_time:.2f} seconds!"
                )
            )

            # Set statement timeout to prevent queries from hanging
            cursor = conn.cursor()
            cursor.execute(f"SET statement_timeout = {timeout * 1000};")  # milliseconds

            # First check if tables exist
            self.stdout.write("Checking if therapy_chunks table exists...")
            cursor.execute("SELECT to_regclass('public.therapy_chunks');")
            chunks_exists = cursor.fetchone()[0] is not None

            self.stdout.write("Checking if therapy_documents table exists...")
            cursor.execute("SELECT to_regclass('public.therapy_documents');")
            documents_exists = cursor.fetchone()[0] is not None

            if not chunks_exists and not documents_exists:
                self.stdout.write(
                    self.style.WARNING("RAG tables don't exist, nothing to do.")
                )
                conn.close()
                # Cancel the alarm
                signal.alarm(0)
                return

            # Check for active connections to these tables
            if not force:
                self.stdout.write("Checking for active connections to these tables...")
                cursor.execute("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND query ~* 'therapy_(chunks|documents)' 
                    AND pid <> pg_backend_pid();
                """)
                active_conn_count = cursor.fetchone()[0]

                if active_conn_count > 0:
                    self.stderr.write(
                        self.style.WARNING(
                            f"Found {active_conn_count} active connections to these tables."
                        )
                    )
                    self.stderr.write(
                        self.style.WARNING("Use --force to drop tables anyway.")
                    )
                    if conn:
                        conn.close()
                    # Cancel the alarm
                    signal.alarm(0)
                    return

            # Drop tables in correct order due to foreign key constraints
            if chunks_exists:
                self.stdout.write("Dropping therapy_chunks table...")
                try:
                    if force:
                        # Add a more aggressive drop that terminates connections
                        cursor.execute("""
                            DO $$ 
                            DECLARE
                                locks_count INTEGER;
                            BEGIN
                                -- Check for locks on the table
                                SELECT COUNT(*) INTO locks_count
                                FROM pg_locks l
                                JOIN pg_class c ON l.relation = c.oid
                                WHERE c.relname = 'therapy_chunks';
                                
                                -- Log locks for debugging
                                RAISE NOTICE 'Found % locks on therapy_chunks table', locks_count;
                                
                                -- Drop the table forcefully, terminating connections
                                EXECUTE 'DROP TABLE IF EXISTS therapy_chunks CASCADE';
                            EXCEPTION WHEN OTHERS THEN
                                RAISE NOTICE 'Error dropping therapy_chunks: %', SQLERRM;
                            END $$;
                        """)
                    else:
                        cursor.execute("DROP TABLE IF EXISTS therapy_chunks;")
                    self.stdout.write(
                        self.style.SUCCESS("therapy_chunks table dropped successfully!")
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error dropping therapy_chunks table: {str(e)}"
                        )
                    )
                    if debug:
                        import traceback

                        self.stderr.write(traceback.format_exc())
                    if not documents_exists:
                        raise

            if documents_exists:
                self.stdout.write("Dropping therapy_documents table...")
                try:
                    if force:
                        # Add a more aggressive drop that terminates connections
                        cursor.execute("""
                            DO $$ 
                            DECLARE
                                locks_count INTEGER;
                            BEGIN
                                -- Check for locks on the table
                                SELECT COUNT(*) INTO locks_count
                                FROM pg_locks l
                                JOIN pg_class c ON l.relation = c.oid
                                WHERE c.relname = 'therapy_documents';
                                
                                -- Log locks for debugging
                                RAISE NOTICE 'Found % locks on therapy_documents table', locks_count;
                                
                                -- Drop the table forcefully, terminating connections
                                EXECUTE 'DROP TABLE IF EXISTS therapy_documents CASCADE';
                            EXCEPTION WHEN OTHERS THEN
                                RAISE NOTICE 'Error dropping therapy_documents: %', SQLERRM;
                            END $$;
                        """)
                    else:
                        cursor.execute("DROP TABLE IF EXISTS therapy_documents;")
                    self.stdout.write(
                        self.style.SUCCESS(
                            "therapy_documents table dropped successfully!"
                        )
                    )
                except Exception as e:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error dropping therapy_documents table: {str(e)}"
                        )
                    )
                    if debug:
                        import traceback

                        self.stderr.write(traceback.format_exc())
                    raise

            # Verify tables were dropped
            self.stdout.write("Verifying tables were dropped...")
            cursor.execute("SELECT to_regclass('public.therapy_chunks');")
            chunks_exists = cursor.fetchone()[0] is not None

            cursor.execute("SELECT to_regclass('public.therapy_documents');")
            documents_exists = cursor.fetchone()[0] is not None

            if chunks_exists or documents_exists:
                self.stderr.write(
                    self.style.ERROR("Tables still exist after drop attempt.")
                )
                self.stderr.write(self.style.ERROR("Try running with --force flag."))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Verified: RAG tables have been successfully reset."
                    )
                )

            conn.commit()
            cursor.close()
            conn.close()
            conn = None
            self.stdout.write(
                self.style.SUCCESS("Database connection closed properly.")
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "RAG tables have been successfully reset. Run setup_therapy_rag command now."
                )
            )

            # Recreate vector store tables with updated embedding dimension
            self.stdout.write("Recreating RAG vector store tables...")
            try:
                from chatbot.services.rag.vector_store import vector_store

                vector_store._setup_vector_store()
                self.stdout.write(
                    self.style.SUCCESS("Vector store tables recreated successfully!")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error recreating vector store tables: {str(e)}")
                )

            # Cancel the alarm since we completed successfully
            signal.alarm(0)

        except psycopg2.OperationalError as e:
            self.stderr.write(self.style.ERROR(f"Database connection error: {str(e)}"))
            self.stderr.write(
                self.style.WARNING("Check your VPN connection and network settings.")
            )
            self.stderr.write(
                self.style.WARNING("Try increasing timeout: --timeout 60")
            )
            self.stderr.write(
                self.style.WARNING("Or try using local database: --local")
            )
            logger.error(
                f"Database connection error in reset_rag_tables: {str(e)}",
                exc_info=True,
            )

            # Cancel the alarm since we're exiting with an error
            signal.alarm(0)
            return 1
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error resetting RAG tables: {str(e)}"))
            if debug:
                import traceback

                self.stderr.write(traceback.format_exc())
            logger.error(f"Error in reset_rag_tables command: {str(e)}", exc_info=True)

            # Cancel the alarm since we're exiting with an error
            signal.alarm(0)
            return 1
        finally:
            # Make sure connection is closed even in case of error
            if conn:
                try:
                    conn.close()
                    self.stdout.write("Database connection closed.")
                except Exception:
                    pass

    def _ensure_dependencies(self):
        """Ensure all required dependencies are installed"""
        # Check for spaCy model
        try:
            import spacy

            try:
                spacy.load("en_core_web_sm")
                self.stdout.write(self.style.SUCCESS("✓ spaCy model found"))
            except IOError:
                self.stdout.write(
                    self.style.WARNING("spaCy model not found. Installing...")
                )
                management.call_command("download_spacy_model")
        except ImportError:
            self.stdout.write(
                self.style.WARNING(
                    "spaCy not installed properly. Please check your installation."
                )
            )

        # You could add other dependency checks here
