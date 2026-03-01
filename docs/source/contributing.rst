Contributing
=============

We welcome contributions to gleplot! This document provides guidelines for contributing to the project.

Getting Started
---------------

1. Fork the repository on GitHub
2. Clone your fork locally:

   .. code-block:: bash

      git clone https://github.com/yourusername/gleplot.git
      cd gleplot

3. Create a virtual environment:

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows: venv\Scripts\activate

4. Install in development mode with dependencies:

   .. code-block:: bash

      pip install -e ".[dev]"

5. Create a new branch for your work:

   .. code-block:: bash

      git checkout -b feature/your-feature-name

Development Workflow
--------------------

Running Tests
~~~~~~~~~~~~~

Run the test suite:

.. code-block:: bash

   pytest

With coverage:

.. code-block:: bash

   pytest --cov=gleplot

Code Style
~~~~~~~~~~~

We use black for code formatting and flake8 for linting.

Format your code:

.. code-block:: bash

   black src/ tests/

Check for linting issues:

.. code-block:: bash

   flake8 src/ tests/

Type Checking
~~~~~~~~~~~~~~

We use mypy for static type checking:

.. code-block:: bash

   mypy src/

Building Documentation
~~~~~~~~~~~~~~~~~~~~~~~

Build the documentation locally:

.. code-block:: bash

   cd docs
   make html

The built HTML will be in ``docs/build/html/``.

Submitting Changes
-------------------

1. Make sure all tests pass:

   .. code-block:: bash

      pytest

2. Ensure code is formatted and passes linting:

   .. code-block:: bash

      black src/ tests/
      flake8 src/ tests/
      mypy src/

3. Update documentation if needed

4. Commit your changes:

   .. code-block:: bash

      git commit -m "Clear, descriptive commit message"

5. Push to your fork:

   .. code-block:: bash

      git push origin feature/your-feature-name

6. Create a Pull Request with a clear description of your changes

Code Guidelines
---------------

- Follow PEP 8 style guide
- Write docstrings for all public functions and classes
- Add tests for new features
- Update documentation for changes in API
- Keep commits atomic and focused

Reporting Issues
----------------

When reporting bugs, please include:

- Your Python version
- Your operating system
- Steps to reproduce the issue
- Expected behavior
- Actual behavior
- Any error messages or tracebacks

Feature Requests
----------------

Feature requests are welcome! Please describe:

- The use case and problem it solves
- Example usage
- Any relevant references or prior art

Code of Conduct
---------------

This project is committed to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

Questions?
----------

If you have questions about contributing, please open an issue or contact the maintainers.

Thank you for contributing to gleplot!
